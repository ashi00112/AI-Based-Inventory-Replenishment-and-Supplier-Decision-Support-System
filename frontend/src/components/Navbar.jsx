import React, { useState, useEffect, useRef } from 'react';
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
  ChevronDown,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import AnimatedBrand from './AnimatedBrand';

const inventorySubLinks = [
  { to: '/products', label: 'Products', description: 'Product catalog & SKUs', icon: Package },
  { to: '/inventory', label: 'Stock Overview', description: 'On-hand, reserved & ROP', icon: Boxes },
  { to: '/transactions', label: 'Transactions', description: 'Stock movements & audit', icon: ArrowRightLeft },
];

export default function Navbar() {
  const { user, isAdmin, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [inventoryOpen, setInventoryOpen] = useState(false);
  const [mobileInventoryOpen, setMobileInventoryOpen] = useState(false);
  const dropdownRef = useRef(null);

  // Close desktop dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event) {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setInventoryOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Close dropdown on route change
  useEffect(() => {
    setInventoryOpen(false);
    setMobileMenuOpen(false);
  }, [location.pathname]);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const isInventoryActive = inventorySubLinks.some((sub) => isActive(sub.to));

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

          {/* Desktop Navigation — Consolidated and Clean */}
          <nav className="hidden lg:flex items-center gap-1 bg-[#01272e]/80 border border-white/[0.08] rounded-full px-2 py-1 shadow-inner">
            {/* Dashboard */}
            <Link
              to="/"
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                isActive('/')
                  ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                  : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
              }`}
            >
              <LayoutDashboard className={`w-3.5 h-3.5 ${isActive('/') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
              <span>Dashboard</span>
            </Link>

            {/* Inventory Dropdown (Products, Stock Overview, Transactions) */}
            <div className="relative" ref={dropdownRef}>
              <button
                type="button"
                onClick={() => setInventoryOpen((prev) => !prev)}
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 cursor-pointer ${
                  isInventoryActive
                    ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                    : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
                }`}
                aria-expanded={inventoryOpen}
              >
                <Boxes className={`w-3.5 h-3.5 ${isInventoryActive ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
                <span>Inventory</span>
                <ChevronDown
                  className={`w-3 h-3 transition-transform duration-200 ${inventoryOpen ? 'rotate-180' : ''} ${
                    isInventoryActive ? 'text-[#03D26F]' : 'text-[#EAF4F4]/50'
                  }`}
                />
              </button>

              {/* Dropdown Menu */}
              {inventoryOpen && (
                <div className="absolute top-full left-0 mt-2 w-56 rounded-2xl bg-[#01272e]/95 border border-white/[0.1] shadow-2xl backdrop-blur-2xl p-1.5 z-50 space-y-0.5 animate-in fade-in slide-in-from-top-1 duration-150">
                  <div className="px-3 py-1.5 text-[10px] font-mono uppercase text-[#EAF4F4]/40 font-semibold tracking-wider">
                    Inventory Management
                  </div>
                  {inventorySubLinks.map(({ to, label, description, icon: SubIcon }) => {
                    const active = isActive(to);
                    return (
                      <Link
                        key={to}
                        to={to}
                        onClick={() => setInventoryOpen(false)}
                        className={`flex items-start gap-2.5 px-3 py-2 rounded-xl text-xs transition-all duration-150 ${
                          active
                            ? 'bg-[#03D26F]/15 text-[#03D26F] font-semibold border border-[#03D26F]/30'
                            : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
                        }`}
                      >
                        <SubIcon className={`w-4 h-4 mt-0.5 shrink-0 ${active ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
                        <div className="leading-tight">
                          <span className="block font-medium">{label}</span>
                          <span className="block text-[10px] text-[#EAF4F4]/50 font-normal mt-0.5">{description}</span>
                        </div>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Suppliers */}
            <Link
              to="/suppliers"
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                isActive('/suppliers')
                  ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                  : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
              }`}
            >
              <Truck className={`w-3.5 h-3.5 ${isActive('/suppliers') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
              <span>Suppliers</span>
            </Link>

            {/* Documents */}
            <Link
              to="/documents"
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                isActive('/documents')
                  ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                  : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
              }`}
            >
              <FileText className={`w-3.5 h-3.5 ${isActive('/documents') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
              <span>Documents</span>
            </Link>

            {/* Decision Intelligence */}
            <Link
              to="/decisions"
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                isActive('/decisions')
                  ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                  : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
              }`}
            >
              <Sparkles className={`w-3.5 h-3.5 ${isActive('/decisions') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
              <span>Decision Intelligence</span>
            </Link>

            {/* AI Assistant */}
            <Link
              to="/assistant"
              className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                isActive('/assistant')
                  ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                  : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
              }`}
            >
              <Bot className={`w-3.5 h-3.5 ${isActive('/assistant') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
              <span>AI Assistant</span>
            </Link>

            {/* Users (Admin Only) */}
            {isAdmin && (
              <Link
                to="/users"
                className={`inline-flex items-center gap-1.5 text-xs font-medium px-3.5 py-1.5 rounded-full transition-all duration-200 ${
                  isActive('/users')
                    ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/40 shadow-sm font-semibold'
                    : 'text-[#EAF4F4]/75 hover:text-white hover:bg-white/[0.06]'
                }`}
              >
                <Users className={`w-3.5 h-3.5 ${isActive('/users') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
                <span>Users</span>
              </Link>
            )}
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
                className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full text-[#EAF4F4]/70 hover:text-rose-300 hover:bg-rose-500/10 border border-transparent hover:border-rose-500/20 transition-all duration-200 cursor-pointer"
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
              className="lg:hidden p-2 rounded-xl text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.08] transition cursor-pointer"
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
          {/* Dashboard */}
          <Link
            to="/"
            onClick={() => setMobileMenuOpen(false)}
            className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              isActive('/')
                ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 font-semibold'
                : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
            }`}
          >
            <LayoutDashboard className={`w-4 h-4 ${isActive('/') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
            <span>Dashboard</span>
          </Link>

          {/* Collapsible Mobile Inventory Group */}
          <div className="rounded-xl overflow-hidden bg-black/20 border border-white/[0.06]">
            <button
              type="button"
              onClick={() => setMobileInventoryOpen((prev) => !prev)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 text-sm font-medium transition-all ${
                isInventoryActive ? 'text-[#03D26F] font-semibold' : 'text-[#EAF4F4]/80 hover:text-white'
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Boxes className={`w-4 h-4 ${isInventoryActive ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
                <span>Inventory</span>
              </div>
              <ChevronDown className={`w-4 h-4 transition-transform duration-200 ${mobileInventoryOpen ? 'rotate-180' : ''}`} />
            </button>

            {mobileInventoryOpen && (
              <div className="px-2 pb-2 pt-1 space-y-1 border-t border-white/[0.06]">
                {inventorySubLinks.map(({ to, label, description, icon: SubIcon }) => {
                  const active = isActive(to);
                  return (
                    <Link
                      key={to}
                      to={to}
                      onClick={() => setMobileMenuOpen(false)}
                      className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-xs transition-all ${
                        active
                          ? 'bg-[#03D26F]/20 text-[#03D26F] font-semibold'
                          : 'text-[#EAF4F4]/70 hover:text-white hover:bg-white/[0.04]'
                      }`}
                    >
                      <SubIcon className={`w-3.5 h-3.5 ${active ? 'text-[#03D26F]' : 'text-[#EAF4F4]/50'}`} />
                      <div>
                        <span>{label}</span>
                        <span className="text-[10px] text-[#EAF4F4]/40 block">{description}</span>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </div>

          {/* Suppliers */}
          <Link
            to="/suppliers"
            onClick={() => setMobileMenuOpen(false)}
            className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              isActive('/suppliers')
                ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 font-semibold'
                : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
            }`}
          >
            <Truck className={`w-4 h-4 ${isActive('/suppliers') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
            <span>Suppliers</span>
          </Link>

          {/* Documents */}
          <Link
            to="/documents"
            onClick={() => setMobileMenuOpen(false)}
            className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              isActive('/documents')
                ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 font-semibold'
                : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
            }`}
          >
            <FileText className={`w-4 h-4 ${isActive('/documents') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
            <span>Documents</span>
          </Link>

          {/* Decision Intelligence */}
          <Link
            to="/decisions"
            onClick={() => setMobileMenuOpen(false)}
            className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              isActive('/decisions')
                ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 font-semibold'
                : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
            }`}
          >
            <Sparkles className={`w-4 h-4 ${isActive('/decisions') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
            <span>Decision Intelligence</span>
          </Link>

          {/* AI Assistant */}
          <Link
            to="/assistant"
            onClick={() => setMobileMenuOpen(false)}
            className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
              isActive('/assistant')
                ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 font-semibold'
                : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
            }`}
          >
            <Bot className={`w-4 h-4 ${isActive('/assistant') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
            <span>AI Assistant</span>
          </Link>

          {/* Users (Admin Only) */}
          {isAdmin && (
            <Link
              to="/users"
              onClick={() => setMobileMenuOpen(false)}
              className={`flex items-center gap-2.5 px-3.5 py-2.5 rounded-xl text-sm font-medium transition-all ${
                isActive('/users')
                  ? 'bg-[#03D26F]/20 text-[#03D26F] border border-[#03D26F]/30 font-semibold'
                  : 'text-[#EAF4F4]/80 hover:text-white hover:bg-white/[0.06]'
              }`}
            >
              <Users className={`w-4 h-4 ${isActive('/users') ? 'text-[#03D26F]' : 'text-[#EAF4F4]/60'}`} />
              <span>Users</span>
            </Link>
          )}

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

