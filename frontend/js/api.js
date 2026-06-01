/**
 * PrintPOS API Layer
 * Communicates with either Google Apps Script or Flask backend.
 *
 * Set the API_URL to your Apps Script Web App URL after deployment.
 * For local Flask testing, use: http://localhost:5000/api
 */

// ─── Configuration ─────────────────────────────────────────────────────────
var CONFIG = {
  // Set this to your Google Apps Script Web App URL after deployment
  // Example: 'https://script.google.com/macros/s/AKfycbw.../exec'
  API_URL: localStorage.getItem('printpos_api_url') || '',

  // Set to 'gas' for Google Apps Script, 'flask' for local Flask backend
  BACKEND: localStorage.getItem('printpos_backend') || 'gas'
};

function setApiUrl(url) {
  CONFIG.API_URL = url;
  localStorage.setItem('printpos_api_url', url);
}

function setBackend(type) {
  CONFIG.BACKEND = type;
  localStorage.setItem('printpos_backend', type);
}

// ─── API Calls ─────────────────────────────────────────────────────────────

function apiCall(method, params, callback) {
  if (CONFIG.BACKEND === 'flask') {
    flaskCall(method, params, callback);
  } else {
    gasCall(method, params, callback);
  }
}

// Google Apps Script backend
function gasCall(action, params, callback) {
  var url = CONFIG.API_URL;
  if (!url) {
    callback({error: 'API URL not configured. Click Settings to configure.'});
    return;
  }

  if (action.startsWith('get') || action === 'getStats' || action === 'getOrder' ||
      action === 'getCustomer' || action === 'getProduct') {
    // GET request
    var query = '?action=' + encodeURIComponent(action);
    if (params) {
      Object.keys(params).forEach(function(k) {
        query += '&' + encodeURIComponent(k) + '=' + encodeURIComponent(params[k]);
      });
    }
    var script = document.createElement('script');
    var cbName = 'jsonp_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
    window[cbName] = function(data) {
      delete window[cbName];
      callback(data);
    };
    script.src = url + query + '&callback=' + cbName;
    script.onerror = function() {
      delete window[cbName];
      callback({error: 'Network error - check API URL'});
    };
    document.head.appendChild(script);
    document.head.removeChild(script);
  } else {
    // POST request
    var xhr = new XMLHttpRequest();
    xhr.open('POST', url, true);
    xhr.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
    xhr.onload = function() {
      try {
        callback(JSON.parse(xhr.responseText));
      } catch(e) {
        callback({error: 'Invalid response from server'});
      }
    };
    xhr.onerror = function() { callback({error: 'Network error'}); };
    params = params || {};
    params.action = action;
    xhr.send('callback=jsonp&' + encodeURIComponent(JSON.stringify(params)));
  }
}

// Flask backend
function flaskCall(endpoint, params, callback) {
  var baseUrl = CONFIG.API_URL || 'http://localhost:5000';
  var xhr = new XMLHttpRequest();

  if (endpoint === 'getCustomers') {
    xhr.open('GET', baseUrl + '/api/customers', true);
    xhr.onload = function() { callback(JSON.parse(xhr.responseText)); };
    xhr.onerror = function() { callback({error: 'Network error'}); };
    xhr.send();
  } else if (endpoint === 'getProducts') {
    xhr.open('GET', baseUrl + '/api/products', true);
    xhr.onload = function() { callback(JSON.parse(xhr.responseText)); };
    xhr.send();
  } else if (endpoint === 'getStats') {
    xhr.open('GET', baseUrl + '/api/stats', true);
    xhr.onload = function() { callback(JSON.parse(xhr.responseText)); };
    xhr.send();
  } else if (endpoint === 'getOrders') {
    xhr.open('GET', baseUrl + '/api/orders', true);
    xhr.onload = function() { callback(JSON.parse(xhr.responseText)); };
    xhr.send();
  } else {
    callback({error: 'Unknown endpoint: ' + endpoint});
  }
}

// ─── Convenience Methods ───────────────────────────────────────────────────

function api_getCustomers(cb) { apiCall('getCustomers', null, cb); }
function api_getProducts(cb) { apiCall('getProducts', null, cb); }
function api_getOrders(cb) { apiCall('getOrders', null, cb); }
function api_getOrder(id, cb) { apiCall('getOrder', {id: id}, cb); }
function api_getExpenses(cb) { apiCall('getExpenses', null, cb); }
function api_getLedger(cb) { apiCall('getLedger', null, cb); }
function api_getStats(cb) { apiCall('getStats', null, cb); }
function api_getCustomers_search(q, cb) { apiCall('getCustomers', {q: q}, cb); }

function api_createCustomer(data, cb) { apiCall('createCustomer', data, cb); }
function api_updateCustomer(data, cb) { apiCall('updateCustomer', data, cb); }
function api_deleteCustomer(id, cb) { apiCall('deleteCustomer', {id: id}, cb); }

function api_createProduct(data, cb) { apiCall('createProduct', data, cb); }
function api_updateProduct(data, cb) { apiCall('updateProduct', data, cb); }
function api_deleteProduct(id, cb) { apiCall('deleteProduct', {id: id}, cb); }
function api_adjustStock(data, cb) { apiCall('adjustStock', data, cb); }

function api_createOrder(data, cb) { apiCall('createOrder', data, cb); }
function api_updateOrderStatus(id, status, cb) { apiCall('updateOrderStatus', {id: id, status: status}, cb); }
function api_recordPayment(data, cb) { apiCall('recordPayment', data, cb); }

function api_createExpense(data, cb) { apiCall('createExpense', data, cb); }
function api_updateExpense(data, cb) { apiCall('updateExpense', data, cb); }
function api_deleteExpense(id, cb) { apiCall('deleteExpense', {id: id}, cb); }
