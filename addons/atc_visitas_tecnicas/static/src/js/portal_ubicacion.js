/** @odoo-module ignore **/
// Botón "Usar mi ubicación actual" del portal de instalaciones. El navegador
// solo da el GPS en sitios HTTPS, así que el botón se muestra únicamente ahí;
// en HTTP el contratista pega el enlace de Google Maps o las coordenadas.
function activarBotonesUbicacion() {
    if (!window.isSecureContext || !navigator.geolocation) {
        return;
    }
    document.querySelectorAll(".o_atc_mi_ubicacion").forEach(function (boton) {
        boton.classList.remove("d-none");
        boton.addEventListener("click", function () {
            const campo = document.getElementById(boton.dataset.target);
            const texto = boton.innerHTML;
            boton.disabled = true;
            boton.textContent = "Obteniendo ubicación…";
            navigator.geolocation.getCurrentPosition(
                function (pos) {
                    campo.value = pos.coords.latitude.toFixed(7) + ", "
                        + pos.coords.longitude.toFixed(7);
                    boton.disabled = false;
                    boton.innerHTML = texto;
                },
                function (err) {
                    boton.disabled = false;
                    boton.innerHTML = texto;
                    alert("No se pudo obtener la ubicación: " + err.message);
                },
                { enableHighAccuracy: true, timeout: 20000 }
            );
        });
    });
}

// El paquete del portal se carga en diferido: puede llegar con la página ya
// cargada.
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", activarBotonesUbicacion);
} else {
    activarBotonesUbicacion();
}
