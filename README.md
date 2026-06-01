# PrintPOS - Integrated POS & Accounting for Printing Business

A complete Point of Sale and Accounting system for small printing businesses, using **Google Sheets as database** and **GitHub Pages as frontend server**.

## Architecture

**Option A: Google Apps Script + GitHub Pages (Recommended)**
```
GitHub Pages (static frontend)
  → Google Apps Script Web App (REST API)
    → Google Sheets (database)
```

**Option B: Flask + Google Sheets**
```
Flask Web App (Python)
  → Google Sheets API (via gspread)
    → Google Sheets (database)
```

---

## Option A: Deploy (No Coding Required)

### 1. Setup Google Sheet
1. Go to [sheets.new](https://sheets.new) to create a new spreadsheet
2. Note the **Spreadsheet ID** from the URL: `https://docs.google.com/spreadsheets/d/`**`SPREADSHEET_ID`**`/edit`

### 2. Deploy Apps Script
1. Open the spreadsheet, go to **Extensions > Apps Script**
2. Delete any code in the editor
3. Copy everything from `apps_script/Code.gs` and paste it
4. Save (Ctrl+S), name the project `PrintPOS`
5. Run `setupSpreadsheet()` once (will ask for permissions)
6. Go to **Deploy > New Deployment**
   - Choose **Web App**
   - Execute as: **Me**
   - Access: **Anyone** (or Anyone with link)
   - Click **Deploy**
7. Copy the **Web App URL** (looks like `https://script.google.com/macros/s/.../exec`)

### 3. Host Frontend on GitHub Pages
1. Create a GitHub repository
2. Upload all files from the `frontend/` folder
3. Go to **Settings > Pages** and enable GitHub Pages from the main branch
4. Your site will be at `https://YOUR_USERNAME.github.io/YOUR_REPO/`

### 4. Configure
1. Open your GitHub Pages site
2. Click **Settings** in the sidebar
3. Paste your Apps Script Web App URL
4. Click **Save**

---

## Option B: Local Flask Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up Google Sheets credentials
# 1. Go to https://console.cloud.google.com
# 2. Create a project, enable Google Sheets API
# 3. Create a Service Account, download JSON key as credentials.json

# Set environment variables
set GOOGLE_SPREADSHEET_ID=your_spreadsheet_id
set GOOGLE_SHEETS_CREDENTIALS=credentials.json

# Run
python app.py
```

---

## Features

| Module | Features |
|--------|----------|
| **POS** | Create orders, add items, apply discounts, record payments |
| **Orders** | View all orders, update status (Pending→In Progress→Completed), print |
| **Customers** | Add/edit/delete customers with contact info |
| **Inventory** | Products & services, stock tracking, stock adjustments |
| **Expenses** | Record expenses by category, vendor tracking |
| **Accounting** | General ledger, auto double-entry journaling |
| **Reports** | Monthly P&L, sales vs expenses analysis |
| **Dashboard** | Overview of sales, expenses, pending orders, low stock alerts |

### Product Categories
- **Printing Services** (design, photocopy, binding, laminating, etc.)
- **Paper** (various sizes and types)
- **Ink/Toner** (cartridges, refills)
- **Supplies** (binding materials, laminating pouches, etc.)

### Accounting
The system uses double-entry bookkeeping:
- **Sales** → Debit Accounts Receivable, Credit Sales Revenue
- **Payments** → Debit Cash/Bank, Credit Accounts Receivable
- **Expenses** → Debit Expense Category, Credit Cash/Bank
- **Stock Adjustments** → Debit/credit Inventory account
