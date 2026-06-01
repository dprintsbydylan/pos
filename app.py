import os
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from sheets_db import SheetsDB
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

db = SheetsDB()


def ensure_connected():
    if db.client is None:
        db.connect()


def today_str():
    return date.today().isoformat()


def now_str():
    return datetime.utcnow().isoformat()


def next_order_no():
    today = date.today()
    prefix = today.strftime('INV%Y%m%d')
    orders = db.all('orders')
    nums = []
    for o in orders:
        if o.get('order_no', '').startswith(prefix):
            try:
                nums.append(int(o['order_no'][-3:]))
            except ValueError:
                pass
    num = max(nums) + 1 if nums else 1
    return f'{prefix}{num:03d}'


def update_order_totals(order_id):
    items = db.filter('order_items', order_id=order_id)
    subtotal = sum(float(i.get('subtotal', 0) or 0) for i in items)
    order = db.get_by_id('orders', order_id)
    discount = float(order.get('discount', 0) or 0)
    tax = round(subtotal * 0.08, 2)
    total = round(subtotal + tax - discount, 2)

    payments = db.filter('payments', order_id=order_id)
    amount_paid = sum(float(p.get('amount', 0) or 0) for p in payments)

    if amount_paid >= total:
        payment_status = 'Paid'
    elif amount_paid > 0:
        payment_status = 'Partially Paid'
    else:
        payment_status = 'Unpaid'

    db.update('orders', order_id, {
        'subtotal': round(subtotal, 2),
        'tax': tax,
        'total': total,
        'amount_paid': round(amount_paid, 2),
        'payment_status': payment_status
    })
    return total


def add_journal_entry(date_val, description, entry_type, account_name, debit, credit,
                      reference_type='', reference_id=''):
    entry = {
        'date': date_val,
        'description': description,
        'entry_type': entry_type,
        'account_name': account_name,
        'debit': debit,
        'credit': credit,
        'reference_type': reference_type,
        'reference_id': str(reference_id),
        'created_at': now_str()
    }
    return db.insert('journal', entry)


# ─── Dashboard ───────────────────────────────────────────────────────────────

@app.route('/')
def dashboard():
    ensure_connected()
    month_start = date.today().replace(day=1).isoformat()

    total_sales = db.sum('orders', 'total', {'payment_status': 'Paid'})
    total_expenses = db.sum('expenses', 'amount')
    all_orders = db.all('orders')
    pending_orders = sum(1 for o in all_orders if o.get('status') not in ('Completed', 'Cancelled'))
    active_customers = len(db.all('customers'))

    recent_orders = db.all('orders', order_by='id', desc=True)[:5]
    recent_expenses = db.all('expenses', order_by='id', desc=True)[:5]

    for o in recent_orders:
        cid = o.get('customer_id')
        if cid:
            c = db.get_by_id('customers', int(cid))
            o['customer_name'] = c['name'] if c else 'Walk-in'
        else:
            o['customer_name'] = 'Walk-in'

    products = db.all('products')
    low_stock = sum(1 for p in products if not p.get('is_service') and float(p.get('stock_qty', 0) or 0) < 10)

    return render_template('dashboard.html',
                           total_sales=total_sales,
                           total_expenses=total_expenses,
                           pending_orders=pending_orders,
                           active_customers=active_customers,
                           recent_orders=recent_orders,
                           recent_expenses=recent_expenses,
                           low_stock=low_stock)


# ─── POS Terminal ────────────────────────────────────────────────────────────

@app.route('/pos')
def pos():
    ensure_connected()
    customers = db.all('customers', order_by='name')
    products = db.all('products', order_by='category')
    return render_template('pos.html', customers=customers, products=products)


@app.route('/pos/create-order', methods=['POST'])
def pos_create_order():
    ensure_connected()
    data = request.get_json()
    customer_id = data.get('customer_id')
    items_data = data.get('items', [])
    discount = float(data.get('discount', 0))

    if not items_data:
        return jsonify({'error': 'No items in order'}), 400

    order_data = {
        'order_no': next_order_no(),
        'customer_id': str(customer_id) if customer_id else '',
        'order_date': now_str(),
        'status': 'Pending',
        'discount': discount,
        'payment_status': 'Unpaid',
        'created_at': now_str()
    }
    order_id = db.insert('orders', order_data)

    for item in items_data:
        product_id = item.get('product_id')
        qty = float(item.get('quantity', 1))
        unit_price = float(item.get('unit_price', 0))
        subtotal = round(qty * unit_price, 2)

        product = None
        if product_id:
            product = db.get_by_id('products', int(product_id))

        oi = {
            'order_id': order_id,
            'product_id': str(product_id) if product_id else '',
            'description': item.get('description') or (product['name'] if product else ''),
            'quantity': qty,
            'unit_price': unit_price,
            'subtotal': subtotal
        }
        db.insert('order_items', oi)

        if product and product.get('is_service') != 'TRUE':
            new_qty = float(product.get('stock_qty', 0) or 0) - qty
            if new_qty < 0:
                new_qty = 0
            db.update('products', int(product_id), {'stock_qty': new_qty})

    update_order_totals(order_id)
    order = db.get_by_id('orders', order_id)

    add_journal_entry(today_str(), f'Sale {order["order_no"]}',
                      'sale', 'Sales Revenue', 0, order['total'],
                      'order', order_id)
    add_journal_entry(today_str(), f'Sale {order["order_no"]}',
                      'sale', 'Accounts Receivable', order['total'], 0,
                      'order', order_id)

    return jsonify({'order_id': order_id, 'order_no': order['order_no']})


@app.route('/pos/orders')
def pos_orders():
    ensure_connected()
    orders = db.all('orders', order_by='id', desc=True)
    for o in orders:
        cid = o.get('customer_id')
        if cid:
            c = db.get_by_id('customers', int(cid))
            o['customer_name'] = c['name'] if c else 'Walk-in'
        else:
            o['customer_name'] = 'Walk-in'
    return render_template('orders.html', orders=orders)


@app.route('/pos/orders/<int:order_id>')
def pos_order_detail(order_id):
    ensure_connected()
    order = db.get_by_id('orders', order_id)
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('pos_orders'))
    items = db.filter('order_items', order_id=order_id)
    payments = db.filter('payments', order_id=order_id)
    cid = order.get('customer_id')
    customer = db.get_by_id('customers', int(cid)) if cid else None
    return render_template('order_detail.html', order=order, items=items,
                           payments=payments, customer=customer)


@app.route('/pos/pay/<int:order_id>', methods=['POST'])
def pos_pay(order_id):
    ensure_connected()
    order = db.get_by_id('orders', order_id)
    if not order:
        flash('Order not found', 'danger')
        return redirect(url_for('pos_orders'))

    amount = float(request.form.get('amount', 0))
    method = request.form.get('method', 'Cash')

    if amount <= 0:
        flash('Invalid payment amount', 'danger')
        return redirect(url_for('pos_order_detail', order_id=order_id))

    payment = {
        'order_id': order_id,
        'amount': round(amount, 2),
        'method': method,
        'payment_date': now_str()
    }
    db.insert('payments', payment)
    update_order_totals(order_id)

    add_journal_entry(today_str(), f'Payment for {order["order_no"]}',
                      'sale', 'Cash/Bank', amount, 0,
                      'order', order_id)
    add_journal_entry(today_str(), f'Payment for {order["order_no"]}',
                      'sale', 'Accounts Receivable', 0, amount,
                      'order', order_id)

    flash(f'Payment of ${amount:.2f} recorded', 'success')
    return redirect(url_for('pos_order_detail', order_id=order_id))


@app.route('/pos/orders/<int:order_id>/status', methods=['POST'])
def pos_update_status(order_id):
    ensure_connected()
    order = db.get_by_id('orders', order_id)
    if order:
        status = request.form.get('status')
        if status:
            db.update('orders', order_id, {'status': status})
    return redirect(url_for('pos_order_detail', order_id=order_id))


# ─── Customers ───────────────────────────────────────────────────────────────

@app.route('/customers')
def customers():
    ensure_connected()
    customers_list = db.all('customers', order_by='name')
    return render_template('customers.html', customers=customers_list)


@app.route('/customers/add', methods=['GET', 'POST'])
def customer_add():
    ensure_connected()
    if request.method == 'POST':
        data = {
            'name': request.form['name'],
            'phone': request.form.get('phone', ''),
            'email': request.form.get('email', ''),
            'address': request.form.get('address', ''),
            'company': request.form.get('company', ''),
            'created_at': now_str()
        }
        db.insert('customers', data)
        flash('Customer added', 'success')
        return redirect(url_for('customers'))
    return render_template('customer_form.html', customer=None)


@app.route('/customers/<int:id>/edit', methods=['GET', 'POST'])
def customer_edit(id):
    ensure_connected()
    c = db.get_by_id('customers', id)
    if not c:
        flash('Customer not found', 'danger')
        return redirect(url_for('customers'))
    if request.method == 'POST':
        db.update('customers', id, {
            'name': request.form['name'],
            'phone': request.form.get('phone', ''),
            'email': request.form.get('email', ''),
            'address': request.form.get('address', ''),
            'company': request.form.get('company', '')
        })
        flash('Customer updated', 'success')
        return redirect(url_for('customers'))
    return render_template('customer_form.html', customer=c)


@app.route('/customers/<int:id>/delete', methods=['POST'])
def customer_delete(id):
    ensure_connected()
    db.delete('customers', id)
    flash('Customer deleted', 'success')
    return redirect(url_for('customers'))


# ─── Products / Inventory ────────────────────────────────────────────────────

@app.route('/inventory')
def inventory():
    ensure_connected()
    products = db.all('products', order_by='category')
    return render_template('inventory.html', products=products)


@app.route('/inventory/add', methods=['GET', 'POST'])
def inventory_add():
    ensure_connected()
    if request.method == 'POST':
        data = {
            'name': request.form['name'],
            'description': request.form.get('description', ''),
            'category': request.form['category'],
            'unit_price': float(request.form.get('unit_price', 0)),
            'cost_price': float(request.form.get('cost_price', 0)),
            'stock_qty': float(request.form.get('stock_qty', 0)),
            'unit': request.form.get('unit', 'pc'),
            'is_service': 'TRUE' if request.form.get('is_service') else 'FALSE',
            'created_at': now_str()
        }
        db.insert('products', data)
        flash('Product added', 'success')
        return redirect(url_for('inventory'))
    return render_template('product_form.html', product=None)


@app.route('/inventory/<int:id>/edit', methods=['GET', 'POST'])
def inventory_edit(id):
    ensure_connected()
    p = db.get_by_id('products', id)
    if not p:
        flash('Product not found', 'danger')
        return redirect(url_for('inventory'))
    if request.method == 'POST':
        db.update('products', id, {
            'name': request.form['name'],
            'description': request.form.get('description', ''),
            'category': request.form['category'],
            'unit_price': float(request.form.get('unit_price', 0)),
            'cost_price': float(request.form.get('cost_price', 0)),
            'stock_qty': float(request.form.get('stock_qty', 0)),
            'unit': request.form.get('unit', 'pc'),
            'is_service': 'TRUE' if request.form.get('is_service') else 'FALSE'
        })
        flash('Product updated', 'success')
        return redirect(url_for('inventory'))
    return render_template('product_form.html', product=p)


@app.route('/inventory/<int:id>/delete', methods=['POST'])
def inventory_delete(id):
    ensure_connected()
    db.delete('products', id)
    flash('Product deleted', 'success')
    return redirect(url_for('inventory'))


@app.route('/inventory/stock-adjust', methods=['POST'])
def inventory_stock_adjust():
    ensure_connected()
    pid = int(request.form.get('product_id'))
    qty = float(request.form.get('quantity', 0))
    reason = request.form.get('reason', '')
    p = db.get_by_id('products', pid)
    if p:
        new_qty = float(p.get('stock_qty', 0) or 0) + qty
        if new_qty < 0:
            new_qty = 0
        db.update('products', pid, {'stock_qty': new_qty})
        cost = float(p.get('cost_price', 0) or 0)
        add_journal_entry(today_str(), f'Stock adjustment: {reason}',
                          'adjustment', 'Inventory', 0, abs(qty * cost),
                          'inventory', pid)
        flash('Stock adjusted', 'success')
    return redirect(url_for('inventory'))


# ─── Accounting ──────────────────────────────────────────────────────────────

@app.route('/accounting')
def accounting():
    ensure_connected()
    month_start = date.today().replace(day=1).isoformat()

    sales = db.sum('orders', 'total', {'payment_status': 'Paid'})
    expenses = db.sum('expenses', 'amount')
    receivables = 0
    for o in db.all('orders'):
        if o.get('payment_status') != 'Paid' and o.get('status') != 'Cancelled':
            receivables += float(o.get('total', 0) or 0) - float(o.get('amount_paid', 0) or 0)

    ledger = db.all('journal', order_by='id', desc=True)[:50]

    expense_categories = {}
    for e in db.all('expenses'):
        cat = e.get('category', 'Other')
        expense_categories[cat] = expense_categories.get(cat, 0) + float(e.get('amount', 0) or 0)

    return render_template('accounting.html',
                           sales=sales,
                           expenses=expenses,
                           receivables=round(receivables, 2),
                           ledger=ledger,
                           expense_categories=expense_categories)


# ─── Expenses ────────────────────────────────────────────────────────────────

@app.route('/expenses')
def expenses():
    ensure_connected()
    month = request.args.get('month', date.today().strftime('%Y-%m'))
    expense_list = db.all('expenses', order_by='date', desc=True)
    total = 0
    categories = {}
    filtered = []
    for e in expense_list:
        if e.get('date', '').startswith(month):
            filtered.append(e)
            total += float(e.get('amount', 0) or 0)
            cat = e.get('category', 'Other')
            categories[cat] = categories.get(cat, 0) + float(e.get('amount', 0) or 0)
    return render_template('expenses.html', expenses=filtered,
                           total=total, categories=categories,
                           current_month=month)


@app.route('/expenses/add', methods=['GET', 'POST'])
def expense_add():
    ensure_connected()
    if request.method == 'POST':
        data = {
            'date': request.form['date'],
            'description': request.form['description'],
            'category': request.form['category'],
            'amount': float(request.form['amount']),
            'vendor': request.form.get('vendor', ''),
            'payment_method': request.form.get('payment_method', ''),
            'receipt_ref': request.form.get('receipt_ref', ''),
            'notes': request.form.get('notes', ''),
            'created_at': now_str()
        }
        eid = db.insert('expenses', data)
        add_journal_entry(data['date'], f'{data["description"]} ({data["category"]})',
                          'expense', data['category'], data['amount'], 0,
                          'expense', eid)
        add_journal_entry(data['date'], f'{data["description"]} ({data["category"]})',
                          'expense', 'Cash/Bank', 0, data['amount'],
                          'expense', eid)
        flash('Expense recorded', 'success')
        return redirect(url_for('expenses'))
    return render_template('expense_form.html', expense=None,
                           default_date=date.today().strftime('%Y-%m-%d'))


@app.route('/expenses/<int:id>/edit', methods=['GET', 'POST'])
def expense_edit(id):
    ensure_connected()
    e = db.get_by_id('expenses', id)
    if not e:
        flash('Expense not found', 'danger')
        return redirect(url_for('expenses'))
    if request.method == 'POST':
        db.update('expenses', id, {
            'date': request.form['date'],
            'description': request.form['description'],
            'category': request.form['category'],
            'amount': float(request.form['amount']),
            'vendor': request.form.get('vendor', ''),
            'payment_method': request.form.get('payment_method', ''),
            'receipt_ref': request.form.get('receipt_ref', ''),
            'notes': request.form.get('notes', '')
        })
        flash('Expense updated', 'success')
        return redirect(url_for('expenses'))
    return render_template('expense_form.html', expense=e,
                           default_date=e.get('date', date.today().strftime('%Y-%m-%d')))


@app.route('/expenses/<int:id>/delete', methods=['POST'])
def expense_delete(id):
    ensure_connected()
    for j in db.filter('journal', reference_type='expense', reference_id=str(id)):
        db.delete('journal', j['id'])
    db.delete('expenses', id)
    flash('Expense deleted', 'success')
    return redirect(url_for('expenses'))


# ─── Reports ─────────────────────────────────────────────────────────────────

@app.route('/reports')
def reports():
    ensure_connected()
    year = request.args.get('year', str(date.today().year))

    monthly_sales = [0] * 12
    monthly_expenses = [0] * 12

    for o in db.all('orders'):
        if o.get('status') == 'Cancelled':
            continue
        od = o.get('order_date', '')
        if od.startswith(year):
            try:
                m = int(od[5:7]) - 1
                if 0 <= m < 12:
                    monthly_sales[m] += float(o.get('total', 0) or 0)
            except (ValueError, IndexError):
                pass

    for e in db.all('expenses'):
        ed = e.get('date', '')
        if ed.startswith(year):
            try:
                m = int(ed[5:7]) - 1
                if 0 <= m < 12:
                    monthly_expenses[m] += float(e.get('amount', 0) or 0)
            except (ValueError, IndexError):
                pass

    profit_loss = [round(monthly_sales[i] - monthly_expenses[i], 2) for i in range(12)]
    total_sales = sum(monthly_sales)
    total_expenses_sum = sum(monthly_expenses)
    net_profit = total_sales - total_expenses_sum

    status_counts = {}
    for o in db.all('orders'):
        s = o.get('status', 'Unknown')
        status_counts[s] = status_counts.get(s, 0) + 1
    orders_by_status = list(status_counts.items())

    return render_template('reports.html',
                           year=year,
                           months=[date(2000, m, 1).strftime('%B') for m in range(1, 13)],
                           monthly_sales=monthly_sales,
                           monthly_expenses=monthly_expenses,
                           profit_loss=profit_loss,
                           total_sales=total_sales,
                           total_expenses=total_expenses_sum,
                           net_profit=net_profit,
                           orders_by_status=orders_by_status)


@app.route('/reports/ledger')
def report_ledger():
    ensure_connected()
    entries = db.all('journal', order_by='id', desc=True)
    total_debits = sum(float(e.get('debit', 0) or 0) for e in entries)
    total_credits = sum(float(e.get('credit', 0) or 0) for e in entries)
    return render_template('ledger.html', entries=entries,
                           total_debits=total_debits, total_credits=total_credits)


# ─── API ─────────────────────────────────────────────────────────────────────

@app.route('/api/products/<int:id>')
def api_product(id):
    ensure_connected()
    p = db.get_by_id('products', id)
    if p:
        return jsonify(p)
    return jsonify({'error': 'Not found'}), 404


@app.route('/api/customers')
def api_customers():
    ensure_connected()
    q = request.args.get('q', '')
    customers = db.all('customers', order_by='name')
    if q:
        ql = q.lower()
        customers = [c for c in customers if ql in c.get('name', '').lower()]
    return jsonify([{
        'id': c.get('id'),
        'name': c.get('name'),
        'phone': c.get('phone', ''),
        'company': c.get('company', '')
    } for c in customers[:10]])


@app.route('/api/stats')
def api_stats():
    ensure_connected()
    total_sales = db.sum('orders', 'total', {'payment_status': 'Paid'})
    total_expenses = db.sum('expenses', 'amount')
    orders = db.all('orders')
    pending = sum(1 for o in orders if o.get('status') not in ('Completed', 'Cancelled'))
    return jsonify({
        'sales': total_sales,
        'expenses': total_expenses,
        'pending_orders': pending,
        'customers': len(db.all('customers'))
    })


@app.context_processor
def utility_processor():
    return {'now': datetime.utcnow(), 'range': range}


if __name__ == '__main__':
    app.run(debug=Config.DEBUG, host=Config.HOST, port=Config.PORT)
