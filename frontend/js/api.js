//api.js
const API_BASE = `http://${window.location.hostname}:5000`;  


// AUTH
async function login(email, password) {
  const res = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });

  const data = await res.json();

  return {
    ok: res.ok,        
    status: res.status, 
    ...data
  };
}


async function register(email, password) {
  const res = await fetch(`${API_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });

  const data = await res.json();

  return {
    ok: res.ok,          
    status: res.status, 
    ...data
  };
}

async function forgotPassword(email) {
  const res = await fetch(`${API_BASE}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  });

  const data = await res.json();

  return {
    ok: res.ok,
    status: res.status,
    ...data
  };
}

async function resetPassword(token, password) {
  const res = await fetch(`${API_BASE}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, password })
  });

  const data = await res.json();

  return {
    ok: res.ok,
    status: res.status,
    ...data
  };
}


// DASHBOARD 
async function getDashboard() {
  const token = localStorage.getItem('access_token');
  if (!token) throw new Error('No access token found');

  const res = await fetch(`${API_BASE}/dashboard`, {  
    method: 'GET',
    headers: { 'Authorization': `Bearer ${token}` }
  });
  if (!res.ok) {
    const err = await res.json();
    throw new Error(err.msg || 'Failed to fetch dashboard');
  }
  return res.json();
}

// PREDICT / UPLOAD FILE
async function uploadFile(file) {
  const token = localStorage.getItem('access_token');
  if (!token) throw new Error('Session expired. Please login again.');

  const formData = new FormData();
  formData.append('file', file);

  const res = await fetch(`${API_BASE}/predict/`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`
    },
    body: formData
  });

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.msg || 'File upload failed');
  }

  return data;
}

// ===== ADMIN =====
function getToken() {
  const token = localStorage.getItem("access_token");
  if (!token) throw new Error("Session expired");
  return token;
}

async function getAdminStats() {
  const res = await fetch(`${API_BASE}/admin/stats`, {
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  if (!res.ok) throw new Error("Failed to load stats");
  return res.json();
}

async function getAllUsers() {
  const res = await fetch(`${API_BASE}/admin/users`, {
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  if (!res.ok) throw new Error("Failed to load users");
  return res.json();
}

async function getAllRecords() {
  const res = await fetch(`${API_BASE}/admin/records`, {
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  if (!res.ok) throw new Error("Failed to load records");
  return res.json();
}

async function apiDeleteUser(userId) {
  const res = await fetch(`${API_BASE}/admin/users/${userId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  if (!res.ok) throw new Error("User delete failed");
}

async function apiDeleteRecord(recordId) {
  const res = await fetch(`${API_BASE}/admin/records/${recordId}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  if (!res.ok) throw new Error("Record delete failed");
}

async function verifyUser(userId, email) {
  if (!confirm(`Verify ${email}?`)) return;
  await fetch(`${API_BASE}/admin/users/${userId}/verify`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` }
  });
  alert(`${email} verified`);
  loadAdmin();
}

async function makeAdmin(userId, email) {
  if (!confirm(`Make ${email} admin?`)) return;

  const res = await fetch(`${API_BASE}/admin/users/${userId}/promote`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` }
  });

  const data = await res.json();
  if (!res.ok) return alert(data.msg || "Failed");

  alert(`${email} is admin now`);
  loadAdmin();
}


async function demoteAdmin(userId, email) {
  if (!confirm(`Remove admin role from ${email}?`)) return;

  const res = await fetch(`${API_BASE}/admin/users/${userId}/demote`, {
    method: "POST",
    headers: { Authorization: `Bearer ${getToken()}` }
  });

  const data = await res.json();
  if (!res.ok) return alert(data.msg || "Failed");

  alert(`${email} is normal user now`);
  loadAdmin();
}


async function fetchAdminImage(fileId) {
  try {
    const res = await fetch(`${API_BASE}/predict/file/${fileId}`, {
      headers: { Authorization: `Bearer ${getToken()}` }
    });
    if (!res.ok) return "placeholder.png";
    return URL.createObjectURL(await res.blob());
  } catch {
    return "placeholder.png";
  }
}