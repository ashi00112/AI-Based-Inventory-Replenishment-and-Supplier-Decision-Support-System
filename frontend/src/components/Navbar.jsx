import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Package,
  Boxes,
  ArrowRightLeft,
  Truck,
  FileText,
  Sparkles,
  Users,
  LogOut,
  Menu,
  X,
  Shield,
  UserCheck,
  Bot,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import AnimatedBrand from './AnimatedBrand';

const baseNavLinks = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/products', label: 'Products', icon: Package },
  { to: '/inventory', label: 'Inventory', icon: Boxes },
  { to: '/transactions', label: 'Transactions', icon: ArrowRightLeft },
  { to: '/suppliers', label: 'Suppliers', icon: Truck },
  { to: '/documents', label: 'Documents', icon: FileText },
  { to: '/decisions', label: 'Decisions', icon: Sparkles },
  { to: '/assistant', label: 'AI Assistant', icon: Bot },
];

export default function Navbar() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const navLinks = [
    ...baseNavLinks,
    ...(isAdmin ? [{ to: '/users', label: 'Users', icon: Users }] : []),
  ];

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  return (
    <header className="sticky top-0 z-50 w-full transition-all">
      {/* Cyprus enterprise glass backdrop */}
      <div className="absolute inset-0 bg-[#01353e]/90 backdrop-blur-xl border-b border-white/[0.08] shadow-sm" />

      <div className="relative max-w-7xl mx-auto px-4 sm:px-6">
        <div className="h-16 flex items-center justify-between gap-4">
          {/* Animated Brand Logo & Name */}
          <Link to="/" className="group flex items-center shrink-0">
            <AnimatedBrand
              size="md"
              subtitle="Autonomous Decision Intelligence"
              showSubtitle={true}
            />
          </Link>

          {/* Desktop Navigation — Cyprus & Malachite pill container */}
          <nav className="hidden lg:flex items-center gap-1 bg-[#01272e]/80 border border-white/[0.08] rounded-full px-2 py-1 shadow-inner">
            {navLinks.map(({ to, label, icon: Icon }) => {
              const active = isActive(to);
              return (
                <Link
                  key={to}
                  to={to}
                  className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                    active
                      ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                      : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${active ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
                  <span>{label}</span>
                </Link>
              );
            })}
          </nav>

          {/* Right section: User Status & Logout */}
          <div className="flex items-center gap-2.5">
            {/* User badge with role indicator */}
            {user && (
              <div className="hidden sm:flex items-center gap-2.5 px-3 py-1.5 rounded-full bg-[#01272e]/80 border border-white/[0.08]">
                <div className="w-6 h-6 rounded-full bg-gradient-to-br from-[#03D26F] to-[#014651] flex items-center justify-center shadow-sm">
                  <span className="text-[10px] font-bold text-white font-mono">
                    {user.name?.charAt(0)?.toUpperCase()}
                  </span>
                </div>
                <div className="text-left leading-tight">
                  <span className="text-xs text-[#EAF4F4] font-medium block truncate max-w-[120px]">
                    {user.name}
                  </span>
                  <span className="text-[9px] font-mono tracking-wider uppercase font-semibold flex items-center gap-1 text-[#CEF431]">
                    {isAdmin ? (
                      <>
                        <Shield className="w-2.5 h-2.5" /> ADMIN
                      </>
                    ) : (
                      <>
                        <UserCheck className="w-2.5 h-2.5" /> STAFF
                      </>
                    )}
                  </span>
                </div>
              </div>
            )}

            {/* Logout CTA */}
            {user && (
              <button
                type="button"
                onClick={handleLogout}
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full text-[#EAF4F4]/70 hover:text-rose-300 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-all duration-200"
                title="Sign Out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden md:inline">Sign Out</span>
              </button>
            )}

            {/* Mobile menu toggle */}
            <button
              type="button"
              onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              className="lg:hidden p-2 rounded-xl text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.08] transition"
              aria-label="Toggle navigation menu"
            >
              {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
            </button>
          </div>
        </div>
      </div>

      {/* Mobile Navigation Drawer */}
      {mobileMenuOpen && (
        <div className="lg:hidden relative bg-[#01353e]/95 backdrop-blur-2xl border-b border-white/[0.08] px-4 pb-4 pt-2 space-y-1 animate-in">
          {navLinks.map(({ to, label, icon: Icon }) => {
            const active = isActive(to);
            return (
              <Link
                key={to}
                to={to}
                onClick={() => setMobileMenuOpen(false)}
                className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                  active
                    ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 font-semibold'
                    : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
                }`}
              >
                <Icon className={`w-4 h-4 ${active ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
                <span>{label}</span>
              </Link>
            );
          })}

          {user && (
            <div className="pt-3 mt-3 border-t border-white/[0.08]">
              <div className="flex items-center gap-2.5 px-3 py-2">
                <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#03D26F] to-[#014651] flex items-center justify-center">
                  <span className="text-xs font-bold text-white font-mono">
                    {user.name?.charAt(0)?.toUpperCase()}
                  </span>
                </div>
                <div>
                  <span className="text-xs text-white font-medium block">{user.name}</span>
                  <span className="text-[10px] text-[#CEF431] font-mono uppercase font-semibold">
                    {user.role}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </header>
  );
}

