# TODO: Corregir claves de sesión inconsistentes en filtros de roles

## Pendientes
- [x] Corregir blueprints/incidentes/routes.py: cambiar "empresa_nit" a "nit_empresa" y 'rol_nombre' a 'rol'
- [x] Corregir utils/permisos.py: cambiar 'rol_nombre' a 'rol' en obtener_usuario_desde_session y requiere_roles
- [x] Verificar que no haya otros lugares con claves inconsistentes
- [ ] Probar que Super Admin vea todos los incidentes y Administrador solo los de su empresa
