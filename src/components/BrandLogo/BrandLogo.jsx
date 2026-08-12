import { useState } from 'react';
import fetalGuardLogo from '../../PKM KC LOGO FETAL GUARD.png';
import './BrandLogo.css';

const VARIANT_CLASS_NAMES = {
  auth: 'brand-logo--auth',
  onboarding: 'brand-logo--onboarding',
  sidebar: 'brand-logo--sidebar',
};

const BrandLogo = ({ variant = 'auth', className = '' }) => {
  const variantClassName = VARIANT_CLASS_NAMES[variant] || VARIANT_CLASS_NAMES.auth;
  const classes = ['brand-logo', variantClassName, className].filter(Boolean).join(' ');
  const [logoFailed, setLogoFailed] = useState(false);

  return (
    <div className={classes}>
      {logoFailed ? (
        <div className="brand-logo__fallback" role="img" aria-label="Logo Fetal-Guard">
          <strong>FETAL-GUARD</strong>
          <span>Smart Maternity Belt</span>
        </div>
      ) : (
        <img
          className="brand-logo__image"
          src={fetalGuardLogo}
          alt="Logo Fetal-Guard"
          decoding="async"
          onError={() => setLogoFailed(true)}
        />
      )}
    </div>
  );
};

export default BrandLogo;
