document.addEventListener('DOMContentLoaded', () => {
    const roles = ["Administrador", "Usuario", "Auditor"];
    const select = document.getElementById("rol");
  
    // Cargar roles dinámicamente
    roles.forEach(rol => {
      const option = document.createElement("option");
      option.value = rol;
      option.textContent =  rol;
      select.appendChild(option);
    });
  
    // Validar y registrar
    document.getElementById('registroForm').addEventListener('submit', function(e) {
      e.preventDefault();
  
      const nit = document.getElementById('nit').value.trim();
      const usuario = document.getElementById('usuario').value.trim();
      const contraseña = document.getElementById('contraseña').value.trim();
      const rol = document.getElementById('rol').value;
  
      const mensaje = document.getElementById('mensaje');
  
      if (!nit || !usuario || !contraseña || !rol) {
        mensaje.textContent = 'Todos los campos son obligatorios.';
        mensaje.style.color = 'red';
        return;
      }
  
      const datos = {
        nit,
        usuario,
        contraseña,
        rol
      };
  
      console.log('Datos registrados:', datos);
      mensaje.textContent = '¡Registro exitoso!';
      mensaje.style.color = 'green';
  
      document.getElementById('registroForm').reset();
    });
  });
  
