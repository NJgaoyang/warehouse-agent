(() => {
  const style = document.createElement('style');
  style.textContent = `
    .statusbar{
      top:86px !important;
      left:50% !important;
      right:auto !important;
      bottom:auto !important;
      transform:translate(-50%,-8px) !important;
      z-index:9999 !important;
      max-width:min(680px,calc(100vw - 320px));
      text-align:center;
      box-shadow:0 8px 24px rgba(15,23,42,.18);
    }
    .statusbar.show{
      transform:translate(-50%,0) !important;
    }
    @media(max-width:900px){
      .statusbar{
        top:74px !important;
        max-width:calc(100vw - 32px);
      }
    }
  `;
  document.head.appendChild(style);
})();
