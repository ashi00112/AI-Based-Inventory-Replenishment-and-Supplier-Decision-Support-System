import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  Boxes,
  ArrowRightLeft,
  Truck,
  LogOut,
  Menu,
  X,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const navLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/inventory', label: 'Inventory', icon: Boxes },
  { to: '/transactions', label: 'Transactions', icon: ArrowRightLeft },
  { to: '/suppliers', label: 'Suppliers', icon: Truck },
];

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <header className="sticky top-0 z-50 w-full">
      {/* Glassmorphism backdrop */}
      <div className="absolute inset-0 bg-neutral-950/70 backdrop-blur-2xl border-b border-white/[0.04]" />

      <div className="relative max-w-6xl mx-auto px-4 sm:px-6">
        <div className="h-16 flex items-center justify-between">
          {/* Logo */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-lg shadow-violet-500/20 group-hover:shadow-violet-500/30 transition-shadow">
              <span className="text-white font-bold text-sm tracking-tight">S</span>
            </div>
            <div className="hidden sm:block">
              <span className="text-sm font-semibold text-white tracking-tight">SmartSupply</span>
              <span className="text-[10px] text-neutral-500 block leading-tight font-medium">Inventory Intelligence</span>
            </div>
          </Link>

          {/* Desktop Navigation — pill-style */}
          <nav className="hidden md:flex items-center gap-1 bg-neutral-900/60 border border-white/[0.06] rounded-full px-1.5 py-1">
            {navLinks.map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                  isActive(to)
                    ? 'bg-violet-500/15 text-violet-300 shadow-sm'
                    : 'text-neutral-400 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                <span>{label}</span>
              </Link>
            ))}
          </nav>

          {/* Right section */}
          <div className="flex items-center gap-2">
            {/* User badge — desktop only */}
            {user && (
              <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.03] border border-white/[0.06]">
                <div className="w-5 h-5 rounded-full bg-gradient-to-br from-teal-400 to-emerald-500 flex items-center justify-center">
                  <span className="text-[9px] font-bold text-white">{user.name?.charAt(0)?.toUpperCase()}</span>
                </div>
                <span className="text-xs text-neutral-300 font-medium">{user.name}</span>
                <span className="text-[9px] text-violet-400 font-medium uppercase tracking-wider">{user.role}</span>
              </div>
            )}

            {/* Logout */}
            {user && (
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-full text-neutral-400 hover:text-red-400 hover:bg-red-500/[0.08] transition-all duration-200"
                title="Sign Out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Logout</span>
              </button>
            )}

            {/* Mobile menu toggle */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="md:hidden p-2 rounded-lg text-neutral-400 hover:text-white hover:bg-white/[0.06] transition"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation */}
      {mobileMenuOpen && (
        <div className="md:hidden relative bg-neutral-950/95 backdrop-blur-xl border-b border-white/[0.04] px-4 pb-4 pt-2 space-y-1 animate-in">
          {navLinks.map(({ to, label, icon: Icon }) => (
            <Link
              key={to}
              to={to}
              onClick={() => setMobileMenuOpen(false)}
              className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive(to)
                  ? 'bg-violet-500/10 text-violet-300'
                  : 'text-neutral-400 hover:text-white hover:bg-white/[0.04]'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{label}</span>
            </Link>
          ))}

          {user && (
            <div className="pt-2 mt-2 border-t border-white/[0.06]">
              <div className="flex items-center gap-2.5 px-3 py-2">
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-teal-400 to-emerald-500 flex items-center justify-center">
                  <span className="text-[10px] font-bold text-white">{user.name?.charAt(0)?.toUpperCase()}</span>
                </div>
                <div>
                  <span className="text-xs text-white font-medium block">{user.name}</span>
                  <span className="text-[10px] text-violet-400 font-medium uppercase">{user.role}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </header>
  );
}
