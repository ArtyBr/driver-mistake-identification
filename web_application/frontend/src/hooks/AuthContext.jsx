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
      const is_verified = authService.getUserIsVerified();
      return { email, is_admin, is_verified };
    }
    return null;
  });
  
  // We can initialize loading to false because we do the check in useState initializer
  const [loading] = useState(false);

  const login = async (email, password) => {
    const data = await authService.login(email, password);
    const is_admin = authService.getUserIsAdmin();
    const is_verified = authService.getUserIsVerified();
    setUser({ email, is_admin, is_verified });
    return data;
  };

  const signup = async (email, password) => {
    return await authService.signup(email, password);
  };

  const verifyEmail = async (token) => {
    const result = await authService.verifyEmail(token);
    // Refresh user state if they are logged in
    if (user) {
      setUser({ ...user, is_verified: true });
      localStorage.setItem('userIsVerified', 'true');
    }
    return result;
  };

  const resendVerification = async () => {
    return await authService.resendVerification();
  };

  const logout = () => {
    authService.logout();
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, signup, verifyEmail, resendVerification, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};
