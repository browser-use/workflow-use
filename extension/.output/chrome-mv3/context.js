var context=function(){"use strict";function i(t){return t}const o={matches:["<all_urls>"],runAt:"document_start",main(){const t=`(
      function() {
        const original = Element.prototype.attachShadow;
        Element.prototype.attachShadow = function(init) {
          if (init && init.mode === 'closed') {
            const newInit = Object.assign({}, init, { mode: 'open' });
            return original.call(this, newInit);
          }
          return original.call(this, init);
        };
      }
    )();`,e=document.createElement("script");e.textContent=t,(document.documentElement||document.head).appendChild(e),e.remove()}};function c(){}function n(t,...e){}const r={debug:(...t)=>n(console.debug,...t),log:(...t)=>n(console.log,...t),warn:(...t)=>n(console.warn,...t),error:(...t)=>n(console.error,...t)};return(async()=>{try{return await o.main()}catch(t){throw r.error('The unlisted script "context" crashed on startup!',t),t}})()}();
context;
