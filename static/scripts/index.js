// -----------------------------
// index.js
// Archivo de scripts para la página de inicio
// -----------------------------

document.addEventListener('DOMContentLoaded', function () {
    // 1. Saludo automático según la hora
    const ahora = new Date();
    const hora = ahora.getHours();
    let saludo = '';

    if (hora < 12) {
        saludo = '¡Buenos días!';
    } else if (hora < 18) {
        saludo = '¡Buenas tardes!';
    } else {
        saludo = '¡Buenas noches!';
    }

    // 2. Mostrar saludo arriba del título si existe <h1>
    const titulo = document.querySelector('h1');
    if (titulo) {
        const saludoElemento = document.createElement('h2');
        saludoElemento.textContent = saludo;
        saludoElemento.classList.add('mb-3', 'text-center');
        titulo.parentNode.insertBefore(saludoElemento, titulo);
    }

    // 3. Efecto de animación al botón al pasar el mouse
    const boton = document.querySelector('.btn-primary');
    if (boton) {
        boton.addEventListener('mouseenter', () => {
            boton.style.transform = 'scale(1.05)';
            boton.style.boxShadow = '0 4px 10px rgba(0, 0, 0, 0.2)';
        });

        boton.addEventListener('mouseleave', () => {
            boton.style.transform = 'scale(1)';
            boton.style.boxShadow = 'none';
        });
    }
});
