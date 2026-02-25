import React, { useState } from 'react';
import { authService } from '../services/authService';
import { AuthContext } from './AuthContextObject';

export const AuthProvider = ({ children }) => {
  // Use initializer to avoid setState in useEffect for initial load
  const [user, setUser] = useState(() => {
    const token = authService.getToken();
    const email = authService.getUserEmail();
    if (token && email) {
      const is_admin = authService.getUserIsAdmin();
      return { email, is_admin };
    }
    return null;
  });
  
  // We can initialize loading to false because we do the check in useState initializer
  const [loading] = useState(false);

  const login = async (email, password) => {
    const data = await authService.login(email, password);
    const is_admin = authService.getUserIsAdmin();
    setUser({ email, is_admin });
    return data;
  };

  const signup = async (email, password) => {
    return await authService.signup(email, password);
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, signup, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};
