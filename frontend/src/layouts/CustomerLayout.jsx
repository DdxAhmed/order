import React from 'react';
import CustomerNavbar from '../components/CustomerNavbar';

export default function CustomerLayout({ children }) {
  return (
    <div className="app-container" style={{ position: 'relative', minHeight: '100vh', background: 'var(--bg)' }}>
      {/* Dynamic 3D Scene Background with animated perspective floor and sparks */}
      <div className="bg-scene" aria-hidden="true">
        <div className="floor"></div>
        <i className="spark" style={{ '--x': '8%', '--s': '4px', '--d': '11s', '--l': '0s' }}></i>
        <i className="spark" style={{ '--x': '24%', '--s': '3px', '--d': '14s', '--l': '3s' }}></i>
        <i className="spark" style={{ '--x': '41%', '--s': '5px', '--d': '12s', '--l': '6s' }}></i>
        <i className="spark" style={{ '--x': '58%', '--s': '3px', '--d': '15s', '--l': '1s' }}></i>
        <i className="spark" style={{ '--x': '73%', '--s': '4px', '--d': '10s', '--l': '4s' }}></i>
        <i className="spark" style={{ '--x': '90%', '--s': '3px', '--d': '13s', '--l': '7s' }}></i>
      </div>

      <CustomerNavbar />

      <main style={{ position: 'relative', zIndex: 1 }}>
        {children}
      </main>
    </div>
  );
}
