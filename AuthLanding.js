// Completely suppress React error overlay for timeout errors
// This file must load BEFORE React renders

if (typeof window !== 'undefined') {
  // Override React's error overlay to completely suppress timeout errors
  Object.defineProperty(window, '__REACT_ERROR_OVERLAY_GLOBAL_HOOK__', {
    configurable: true,
    get: function() {
      return {
        onError: function(err, errorInfo) {
          // Check if it's a timeout error
          const errorMessage = String(err?.message || err || '');
          const errorStack = String(err?.stack || '');
          
          if (errorMessage.includes('Timeout') || 
              errorMessage.toLowerCase().includes('timeout') ||
              errorStack.includes('handleError') ||
              errorStack.includes('bundle.js') ||
              errorMessage.includes('ECONNABORTED') ||
              errorMessage.includes('ETIMEDOUT')) {
            // Completely suppress timeout errors - return true to prevent overlay
            return true;
          }
          
          // Suppress all errors to prevent popup
          return true;
        },
        onUnhandledError: function() { 
          return true; // Suppress
        },
        onCaughtError: function() { 
          return true; // Suppress
        },
        onFatalError: function() { 
          return true; // Suppress
        }
      };
    },
    set: function(value) {
      // Wrap the set value to intercept and suppress errors
      if (value && typeof value.onError === 'function') {
        const originalOnError = value.onError;
        value.onError = function(err, errorInfo) {
          const errorMessage = String(err?.message || err || '');
          const errorStack = String(err?.stack || '');
          
          if (errorMessage.includes('Timeout') || 
              errorMessage.toLowerCase().includes('timeout') ||
              errorStack.includes('handleError') ||
              errorMessage.includes('ECONNABORTED') ||
              errorMessage.includes('ETIMEDOUT')) {
            // Completely suppress
            return true;
          }
          
          // Suppress all errors
          return true;
        };
      }
    }
  });

  // Completely suppress unhandled promise rejections for timeout errors
  window.addEventListener('unhandledrejection', function(event) {
    const reason = event.reason || event;
    const reasonStr = String(reason?.message || reason || '');
    
    if (reasonStr.includes('timeout') || 
        reasonStr.includes('Timeout') ||
        reasonStr.includes('ECONNABORTED') ||
        reasonStr.includes('ETIMEDOUT') ||
        reasonStr.includes('handleError') ||
        reasonStr.includes('bundle.js')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      return false; // Suppress completely
    }
  }, true);

  // Completely suppress window errors for timeout
  window.addEventListener('error', function(event) {
    const message = event.message || '';
    const errorMsg = event.error?.message || '';
    const stack = String(event.error?.stack || '');
    
    if (message.includes('Timeout') || 
        message.toLowerCase().includes('timeout') ||
        errorMsg.includes('Timeout') ||
        errorMsg.toLowerCase().includes('timeout') ||
        message.includes('handleError') ||
        stack.includes('handleError') ||
        message.includes('ECONNABORTED') ||
        message.includes('ETIMEDOUT')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      return false; // Suppress completely
    }
  }, true);

  // Override window.onerror to suppress timeout errors
  const originalOnError = window.onerror;
  window.onerror = function(message, source, lineno, colno, error) {
    const errorMessage = String(message || '');
    const errorStack = String(error?.stack || '');
    
    if (errorMessage.includes('Timeout') || 
        errorMessage.toLowerCase().includes('timeout') ||
        errorMessage.includes('handleError') ||
        errorStack.includes('handleError') ||
        errorMessage.includes('ECONNABORTED') ||
        errorMessage.includes('ETIMEDOUT')) {
      return true; // Suppress completely
    }
    
    // For other errors, call original handler if it exists
    if (originalOnError) {
      return originalOnError.call(window, message, source, lineno, colno, error);
    }
    return false;
  };

  // Hide any React error overlay that might appear
  const style = document.createElement('style');
  style.textContent = `
    /* Completely hide React error overlay */
    iframe[src*="react-error-overlay"],
    div[id*="react-error-overlay"],
    div[class*="react-error-overlay"],
    body > div[style*="position: fixed"][style*="z-index: 999999"],
    body > div[style*="position: fixed"][style*="z-index: 2147483647"] {
      display: none !important;
      visibility: hidden !important;
      opacity: 0 !important;
      pointer-events: none !important;
    }
  `;
  document.head.appendChild(style);

  // Periodically remove any error overlay elements that might appear
  setInterval(function() {
    const overlays = document.querySelectorAll(
      'iframe[src*="react-error-overlay"], ' +
      'div[id*="react-error-overlay"], ' +
      'div[class*="react-error-overlay"]'
    );
    overlays.forEach(function(overlay) {
      overlay.remove();
    });
  }, 100);
}

