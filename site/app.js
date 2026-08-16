(function () {
  'use strict';

  let ticking = false;

  function updateScroll() {
    document.documentElement.style.setProperty('--scroll', window.scrollY);
    ticking = false;
  }

  function requestTick() {
    if (!ticking) {
      requestAnimationFrame(updateScroll);
      ticking = true;
    }
  }

  function initParallax() {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    window.addEventListener('scroll', requestTick, { passive: true });
    requestTick();
  }

  function initReveal() {
    const revealElements = document.querySelectorAll('.reveal');
    if (!window.IntersectionObserver) {
      revealElements.forEach(el => el.classList.add('is-in'));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-in');
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.15,
      rootMargin: '0px 0px -60px 0px'
    });

    revealElements.forEach(el => observer.observe(el));
  }

  function initLanguage() {
    const langButtons = document.querySelectorAll('.lang');
    if (!langButtons.length) return;

    const savedLang = localStorage.getItem('hds.lang');
    if (savedLang && window.I18N && window.I18N[savedLang]) {
      setLanguage(savedLang);
      // Keep the active-language indicator in sync with the restored language,
      // not just on click — otherwise EN stays highlighted while UK is shown.
      langButtons.forEach(btn => {
        btn.setAttribute('aria-pressed', btn.dataset.lang === savedLang ? 'true' : 'false');
      });
    }

    langButtons.forEach(button => {
      button.addEventListener('click', () => {
        const lang = button.dataset.lang;
        if (!window.I18N || !window.I18N[lang]) return;
        setLanguage(lang);
        langButtons.forEach(btn => {
          btn.setAttribute('aria-pressed', btn === button ? 'true' : 'false');
        });
        localStorage.setItem('hds.lang', lang);
      });
    });
  }

  function setLanguage(lang) {
    if (!window.I18N || !window.I18N[lang]) return;
    const dict = window.I18N[lang];
    document.documentElement.lang = lang;
    const i18nElements = document.querySelectorAll('[data-i18n]');
    i18nElements.forEach(el => {
      const key = el.dataset.i18n;
      if (dict[key] !== undefined) {
        el.textContent = dict[key];
      }
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    initParallax();
    initReveal();
    initLanguage();
  });
})();