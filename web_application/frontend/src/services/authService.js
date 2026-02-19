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

  logout() {
    localStorage.removeItem('token');
    localStorage.removeItem('userEmail');
  },

  getToken() {
    return localStorage.getItem('token');
  },

  getUserEmail() {
    return localStorage.getItem('userEmail');
  },

  isAuthenticated() {
    return !!this.getToken();
  }
};
