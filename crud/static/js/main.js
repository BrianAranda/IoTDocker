
// Selector de tema claro/oscuro (persiste en localStorage, claro por defecto)
function aplicarTema(tema) {
  document.documentElement.setAttribute('data-bs-theme', tema);
  localStorage.setItem('tema', tema);
}

const opcionesTema = document.querySelectorAll('.theme-option');
opcionesTema.forEach((opcion) => {
  opcion.addEventListener('click', () => {
    aplicarTema(opcion.getAttribute('data-tema'));
  });
});

const btnDelete= document.querySelectorAll('.btn-borrar');
if(btnDelete) {
  const btnArray = Array.from(btnDelete);
  btnArray.forEach((btn) => {
    btn.addEventListener('click', (e) => {
      if(!confirm('¿Está seguro de querer borrar?')){
        e.preventDefault();
      }
    });
  })
}
