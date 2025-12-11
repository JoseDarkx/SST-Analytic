
    // Script para enviar datos del formulario de recuperación y simular respuesta

    document.getElementById("formRecuperar").addEventListener("submit", function (event) {
    event.preventDefault(); // Evita que el formulario recargue la página

    const nit = document.getElementById("nit").value.trim();
    const correo = document.getElementById("correo").value.trim();
    const mensaje = document.getElementById("mensaje");

    // Validación básica
    if (!nit || !correo) {
        mensaje.textContent = "Todos los campos son obligatorios.";
        mensaje.classList.remove("text-success");
        mensaje.classList.add("text-danger");
        return;
    }

    // Simulación de envío (aquí llamariamos al backend con fetch si estuviera conectado)
    mensaje.textContent = "Se ha enviado un enlace de recuperación al correo registrado.";
    mensaje.classList.remove("text-danger");
    mensaje.classList.add("text-success");

    // Limpieza del formulario
    document.getElementById("formRecuperar").reset();
    });