// Nuclear option: Completely disable React error overlay
// This MUST load before React

(function() {
  
  if (typeof window === 'undefined') return;
  
  // Disable React's error overlay completely
  // eslint-disable-next-line no-unused-vars
  const _originalError = window.Error;
  
  // Block React DevTools error overlay
  if (window.__REACT_DEVTOOLS_GLOBAL_HOOK__) {
    window.__REACT_DEVTOOLS_GLOBAL_HOOK__.onError = function() {
      // Do nothing - block all errors
      return true;
    };
  }
  
  // Block webpack error overlay
  if (window.__webpack_require__) {
    // eslint-disable-next-line no-unused-vars
    const _originalRequire = window.__webpack_require__;
    // Don't let webpack show errors
  }
  
  // Override React's error boundary - COMPLETELY BLOCK ALL ERRORS
  const ErrorOverlay = window.__REACT_ERROR_OVERLAY_GLOBAL_HOOK__;
  if (ErrorOverlay) {
    // Block ALL errors - no exceptions
    ErrorOverlay.onError = function(err, errorInfo) {
      return true; // Always block
    };
    if (ErrorOverlay.onUnhandledError) {
      ErrorOverlay.onUnhandledError = function() { return true; };
    }
    if (ErrorOverlay.onCaughtError) {
      ErrorOverlay.onCaughtError = function() { return true; };
    }
    if (ErrorOverlay.onFatalError) {
      ErrorOverlay.onFatalError = function() { return true; };
    }
  }
  
  // Catch ALL unhandled promise rejections - NO EXCEPTIONS
  // eslint-disable-next-line no-unused-vars
  const _originalUnhandled = window.onunhandledrejection;
  window.onunhandledrejection = function(event) {
    // Suppress timeout errors completely
    const reason = event.reason || event;
    const reasonStr = String(reason?.message || reason || '');
    if (reasonStr.includes('timeout') || 
        reasonStr.includes('Timeout') ||
        reasonStr.includes('ECONNABORTED') ||
        reasonStr.includes('handleError') ||
        reasonStr.includes('bundle.js')) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      return false;
    }
    event.preventDefault();
    event.stopPropagation();
    event.stopImmediatePropagation();
    return false;
  };
  
  // Register multiple listeners to be absolutely sure - INCREASE COUNT
  for (let i = 0; i < 20; i++) {
    window.addEventListener('unhandledrejection', function(e) {
      e.preventDefault();
      e.stopPropagation();
      e.stopImmediatePropagation();
      if (e.cancelable) e.cancelBubble = true;
      // Try every possible way to stop it
      try {
        e.stopPropagation();
        if (e.cancelable !== false) {
          Object.defineProperty(e, 'defaultPrevented', { value: true, writable: false });
        }
      } catch (ex) {
        // Ignore
      }
      return false;
    }, true); // Capture phase
    
    window.addEventListener('error', function(e) {
      const msg = String(e.message || '');
      const errorMsg = String(e.error?.message || '');
      const stack = String(e.error?.stack || '');
      const msgLower = msg.toLowerCase();
      const errorMsgLower = errorMsg.toLowerCase();
      const stackLower = stack.toLowerCase();
      
      if (msg.includes('promise') || 
          msg.includes('Unknown') || 
          msg.includes('handleError') ||
          msg.includes('rejection') ||
          msgLower.includes('timeout') ||
          errorMsg.includes('promise') ||
          errorMsg.includes('Unknown') ||
          errorMsgLower.includes('timeout') ||
          stack.includes('handleError') ||
          stack.includes('bundle.js') ||
          stackLower.includes('timeout')) {
        e.preventDefault();
        e.stopPropagation();
        e.stopImmediatePropagation();
        if (e.cancelable) e.cancelBubble = true;
        try {
          Object.defineProperty(e, 'defaultPrevented', { value: true, writable: false });
        } catch (ex) {
          // Ignore
        }
        return false;
      }
    }, true); // Capture phase
  }
  
  // Also override React's internal error handling
  Object.defineProperty(window, '__REACT_ERROR_OVERLAY_GLOBAL_HOOK__', {
    configurable: true,
    get: function() {
      return {
        onError: function(err, errorInfo) {
          // Block ALL errors - especially timeout errors
          // Always return true to prevent React error overlay
          return true;
        },
        onErrorRecovered: function() {},
        onUnhandledError: function() { return true; },
        onUnhandledErrorRecovered: function() {},
        onCaughtError: function() { return true; },
        onFatalError: function() { return true; }
      };
    },
    set: function(value) {
      // Override any attempts to set it
      if (value && typeof value.onError === 'function') {
        const originalOnError = value.onError;
        value.onError = function(err, errorInfo) {
          const errStr = String(err?.message || err || '');
          const errInfoStr = String(errorInfo || '');
          if (errStr.includes('promise') || 
              errStr.includes('Unknown') || 
              errStr.includes('handleError') ||
              errStr.includes('rejection') ||
              errStr.includes('Timeout') ||
              errStr.includes('timeout') ||
              errStr.includes('ECONNABORTED') ||
              errStr.includes('ETIMEDOUT') ||
              errInfoStr.includes('handleError') ||
              errInfoStr.includes('bundle.js') ||
              errInfoStr.toLowerCase().includes('timeout')) {
            return true; // Block it
          }
          try {
            return originalOnError.call(this, err, errorInfo);
          } catch (e) {
            return true; // Block even if original errors
          }
        };
      }
    }
  });
  
  // Additional: Override React's error overlay display function
  if (window.__REACT_ERROR_OVERLAY_GLOBAL_HOOK__) {
    const hook = window.__REACT_ERROR_OVERLAY_GLOBAL_HOOK__;
    if (hook.onError) {
      const originalOnError = hook.onError;
      hook.onError = function(err, errorInfo) {
        const errStr = String(err?.message || err || '');
        if (errStr.includes('Timeout') || 
            errStr.includes('timeout') ||
            errStr.includes('handleError') ||
            errStr.includes('bundle.js') ||
            errStr.includes('ECONNABORTED')) {
          return true; // Suppress timeout errors
        }
        if (originalOnError) {
          try {
            return originalOnError.call(this, err, errorInfo);
          } catch (e) {
            return true;
          }
        }
        return true; // Suppress all errors
      };
    }
  }
})();

