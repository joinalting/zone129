(function() {
  var PASS = 'altadena2026';
  var KEY = 'ting-access';
  if (sessionStorage.getItem(KEY) === PASS) return;
  var input = prompt('Password:');
  if (input === PASS) {
    sessionStorage.setItem(KEY, PASS);
  } else {
    document.body.innerHTML = '<div style="font-family:DM Sans,sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;color:#6b7563;background:#1A2316;"><p>Access denied.</p></div>';
  }
})();
