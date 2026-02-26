const API_BASE_URL = ''; // Proxy handles routing to the backend

export const authService = {
  async login(email, password) {
    const formData = new URLSearchParams();
    formData.append('username', email); // OAuth2PasswordRequestForm expects 'username'
    formData.append('password', password);

    const response = await fetch(`${API_BASE_URL}/login`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    if (data.access_token) {
      localStorage.setItem('token', data.access_token);
      localStorage.setItem('userEmail', email);

      // Fetch user profile to get is_admin and is_verified flags
      try {
        const meRes = await fetch(`${API_BASE_URL}/me`, {
          headers: { Authorization: `Bearer ${data.access_token}` },
        });
        if (meRes.ok) {
          const me = await meRes.json();
          localStorage.setItem('userIsAdmin', me.is_admin ? 'true' : 'false');
          localStorage.setItem('userIsVerified', me.is_verified ? 'true' : 'false');
        }
      } catch {
        localStorage.setItem('userIsAdmin', 'false');
        localStorage.setItem('userIsVerified', 'false');
      }
    }
    return data;
  },

  async signup(email, password) {
    const response = await fetch(`${API_BASE_URL}/signup`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Signup failed');
    }

    return response.json();
  },

  async verifyEmail(token) {
    const response = await fetch(`${API_BASE_URL}/verify-email?token=${token}`);
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Verification failed');
    }
    return response.json();
  },

  async resendVerification() {
    const token = this.getToken();
    const response = await fetch(`${API_BASE_URL}/resend-verification`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
      },
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to resend verification');
    }
    return response.json();
  },

  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
    localStorage.removeItem('userIsAdmin');
    localStorage.removeItem('userIsVerified');
  },

  getToken() {
    return localStorage.getItem('token');
  },

  getUserEmail() {
    return localStorage.getItem('userEmail');
  },

  getUserIsAdmin() {
    return localStorage.getItem('userIsAdmin') === 'true';
  },

  getUserIsVerified() {
    return localStorage.getItem('userIsVerified') === 'true';
  },

  isAuthenticated() {
    return !!this.getToken();
  }
};
