from urllib.parse import quote

from odoo import fields, http
from odoo.tools import date_utils
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request

from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager

from ..models.atc_vendedor import ESTADOS_EN_PROCESO
from ..models.atc_visita import CAMPOS_PORTAL, ESTADOS_ABIERTOS_PORTAL
from ..models.ubicacion import leer_ubicacion

PASO = 20
CAMPOS_FECHA = ("fecha_programada", "fecha_instalacion")
CAMPOS_ENTEROS = ("metros_fibra",)
CAMPOS_DECIMALES = ("potencia_rx",)
CAMPOS_ETIQUETAS = ("motivo_no_realizada_ids",)
# Pines de ubicación: el formulario envía un texto (coordenadas o enlace de
# Google Maps) que se convierte en latitud/longitud.
PINES = {
    "ubicacion_cliente": ("cliente_latitud", "cliente_longitud", "del cliente"),
    "ubicacion_nap": ("nap_latitud", "nap_longitud", "de la caja NAP"),
}
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre")


class AtcInstalacionPortal(CustomerPortal):

    def _instalaciones_domain(self):
        # Las reglas de portal dejan ver también las ventas del usuario
        # (vendedor): aquí solo las de su contratista. El portal no lee
        # atc.contratista, por eso se resuelve con sudo.
        contratistas = request.env["atc.contratista"].sudo().search(
            [("user_ids", "in", request.env.user.ids)])
        return [("tipo_orden", "=", "instalacion"),
                ("contratista_id", "in", contratistas.ids)]

    def _realizadas_mes_domain(self):
        """Instalaciones hechas en el mes en curso (por fecha de instalación).
        Cuentan también las que están en garantía: se instalaron igual."""
        hoy = fields.Date.context_today(request.env["atc.visita"])
        return [("estado", "in", ("realizada", "garantia")),
                ("fecha_instalacion", ">=", date_utils.start_of(hoy, "month")),
                ("fecha_instalacion", "<=", date_utils.end_of(hoy, "month"))]

    def _nombre_mes_actual(self):
        hoy = fields.Date.context_today(request.env["atc.visita"])
        return "%s %s" % (MESES[hoy.month - 1], hoy.year)

    def _ventas_domain(self):
        vendedores = request.env["atc.vendedor"].sudo().search(
            [("user_ids", "in", request.env.user.ids)])
        return [("tipo_orden", "=", "instalacion"),
                ("vendedor_id", "in", vendedores.ids)]

    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "instalacion_count" in counters:
            Visita = request.env["atc.visita"]
            values["instalacion_count"] = Visita.search_count(
                self._instalaciones_domain()
                + [("estado", "in", ESTADOS_ABIERTOS_PORTAL)]) \
                if Visita.has_access("read") else 0
        if "instalacion_mes_count" in counters:
            Visita = request.env["atc.visita"]
            values["instalacion_mes_count"] = Visita.search_count(
                self._instalaciones_domain() + self._realizadas_mes_domain()) \
                if Visita.has_access("read") else 0
        if "venta_count" in counters:
            Visita = request.env["atc.visita"]
            values["venta_count"] = Visita.search_count(
                self._ventas_domain()
                + [("estado", "in", ESTADOS_EN_PROCESO)]) \
                if Visita.has_access("read") else 0
        return values

    @http.route(["/my/instalaciones", "/my/instalaciones/page/<int:page>"],
                type="http", auth="user", website=True)
    def portal_my_instalaciones(self, page=1, sortby=None, filterby=None,
                                search=None, search_in="todo", **kw):
        Visita = request.env["atc.visita"]
        _ = request.env._
        searchbar_sortings = {
            "antiguedad": {"label": _("Más antiguas primero"),
                           "order": "fecha_asignacion asc, id asc"},
            "recientes": {"label": _("Más recientes primero"),
                          "order": "fecha_asignacion desc, id desc"},
            "programada": {"label": _("Fecha programada"),
                           "order": "fecha_programada asc, id asc"},
        }
        searchbar_filters = {
            "abiertas": {"label": _("Por hacer"),
                         "domain": [("estado", "in", ESTADOS_ABIERTOS_PORTAL)]},
            "garantia": {"label": _("Visitas por garantía"),
                         "domain": [("estado", "=", "garantia")]},
            "realizadas_mes": {"label": _("Realizadas este mes"),
                               "domain": self._realizadas_mes_domain()},
            "realizadas": {"label": _("Realizadas"),
                           "domain": [("estado", "=", "realizada")]},
            "no_realizadas": {"label": _("No realizadas"),
                              "domain": [("estado", "=", "no_realizada")]},
            "todas": {"label": _("Todas"), "domain": []},
        }
        searchbar_inputs = {
            "todo": {"input": "todo", "label": _("Cliente, cédula o dirección")},
        }
        sortby = sortby if sortby in searchbar_sortings else "antiguedad"
        filterby = filterby if filterby in searchbar_filters else "abiertas"

        domain = self._instalaciones_domain() \
            + searchbar_filters[filterby]["domain"]
        if search:
            domain += ["|", "|", ("nombre", "ilike", search),
                       ("cedula", "ilike", search),
                       ("direccion", "ilike", search)]

        total = Visita.search_count(domain)
        pager = portal_pager(
            url="/my/instalaciones",
            url_args={"sortby": sortby, "filterby": filterby,
                      "search": search, "search_in": search_in},
            total=total, page=page, step=PASO)
        instalaciones = Visita.search(
            domain, order=searchbar_sortings[sortby]["order"],
            limit=PASO, offset=pager["offset"])
        request.session["my_instalaciones_history"] = instalaciones.ids[:100]

        values = self._prepare_portal_layout_values()
        values.update({
            "realizadas_mes": Visita.search_count(
                self._instalaciones_domain() + self._realizadas_mes_domain()),
            "mes_actual": self._nombre_mes_actual(),
            "instalaciones": instalaciones.sudo(),
            "page_name": "instalaciones",
            "default_url": "/my/instalaciones",
            "pager": pager,
            "searchbar_sortings": searchbar_sortings,
            "sortby": sortby,
            "searchbar_filters": searchbar_filters,
            "filterby": filterby,
            "searchbar_inputs": searchbar_inputs,
            "search_in": search_in,
            "search": search,
        })
        return request.render(
            "atc_visitas_tecnicas.portal_my_instalaciones", values)

    def _instalacion_check(self, orden_id):
        orden_sudo = self._document_check_access("atc.visita", orden_id)
        if orden_sudo.tipo_orden != "instalacion":
            raise MissingError(request.env._("Esta orden no existe."))
        # La regla de portal también deja leer al vendedor: editar (y ver
        # la ficha del contratista) solo los usuarios del contratista.
        if request.env.user not in orden_sudo.contratista_id.user_ids:
            raise AccessError(request.env._("Esta orden no es de tu contratista."))
        return orden_sudo

    @http.route(["/my/instalaciones/<int:orden_id>"],
                type="http", auth="user", website=True)
    def portal_my_instalacion(self, orden_id, **kw):
        try:
            orden_sudo = self._instalacion_check(orden_id)
        except (AccessError, MissingError):
            return request.redirect("/my/instalaciones")
        values = self._prepare_portal_layout_values()
        values.update({
            "orden": orden_sudo,
            "motivos": request.env["atc.motivo.no.realizada"].sudo().search([]),
            "page_name": "instalacion",
            "puede_editar": orden_sudo._portal_puede_editar(),
            "error": kw.get("error"),
            "success": kw.get("success"),
            # token para que el chatter del portal (fotos y comentarios)
            # pueda publicar en la orden
            "token": orden_sudo._portal_ensure_token(),
        })
        values = self._get_page_view_values(
            orden_sudo, orden_sudo.access_token, values,
            "my_instalaciones_history", False)
        return request.render(
            "atc_visitas_tecnicas.portal_my_instalacion", values)

    def _leer_formulario(self, post):
        vals = {}
        for campo in CAMPOS_PORTAL:
            if campo in CAMPOS_ETIQUETAS:
                # Casillas: llegan repetidas y, si no se marca ninguna, no
                # llegan; el campo oculto "<campo>_enviado" indica que el
                # formulario las incluía para poder vaciarlas.
                if campo + "_enviado" not in post:
                    continue
                ids = [int(i) for i in
                       request.httprequest.form.getlist(campo)]
                Modelo = request.env[
                    request.env["atc.visita"]._fields[campo].comodel_name]
                vals[campo] = [(6, 0, Modelo.sudo().browse(ids).exists().ids)]
                continue
            if campo not in post:
                continue
            valor = (post.get(campo) or "").strip()
            if campo in CAMPOS_FECHA:
                vals[campo] = fields.Date.to_date(valor) if valor else False
            elif campo in CAMPOS_ENTEROS:
                vals[campo] = int(valor) if valor else 0
            elif campo in CAMPOS_DECIMALES:
                vals[campo] = float(valor.replace(",", ".")) if valor else 0.0
            else:
                vals[campo] = valor or False
        for entrada, (campo_lat, campo_lng, que) in PINES.items():
            if entrada not in post:
                continue
            try:
                coords = leer_ubicacion(post.get(entrada))
            except ValueError:
                raise ValidationError(request.env._(
                    "No se entendió la ubicación %(que)s. Pega el enlace de "
                    "Google Maps o las coordenadas, p. ej. 10.0661, -69.3207.",
                    que=que))
            vals[campo_lat], vals[campo_lng] = coords or (0.0, 0.0)
        return vals

    @http.route(["/my/instalaciones/<int:orden_id>/actualizar"],
                type="http", auth="user", methods=["POST"], website=True)
    def portal_my_instalacion_actualizar(self, orden_id, **post):
        try:
            orden_sudo = self._instalacion_check(orden_id)
        except (AccessError, MissingError):
            return request.redirect("/my/instalaciones")
        url = "/my/instalaciones/%s" % orden_id
        accion = post.get("accion")
        if accion not in ("guardar", "realizada", "no_realizada", "garantia_atendida"):
            accion = "guardar"
        try:
            vals = self._leer_formulario(post)
            # Escribe con el uid del contratista (queda como autor en el
            # historial) pero con permisos elevados: los campos permitidos
            # los filtra _portal_actualizar. El savepoint descarta cualquier
            # escritura parcial si una validación falla.
            with request.env.cr.savepoint():
                orden_sudo.with_user(request.env.user).sudo()._portal_actualizar(
                    vals, accion=None if accion == "guardar" else accion)
        except (ValueError, ValidationError) as exc:
            msg = exc.args[0] if isinstance(exc, ValidationError) \
                else request.env._("Revisa los valores numéricos y las fechas.")
            return request.redirect(url + "?error=%s" % quote(msg))
        return request.redirect(url + "?success=1")

    # ------------------------------------------------------------------
    # Ventas (vendedores): solo lectura
    # ------------------------------------------------------------------
    @http.route(["/my/ventas", "/my/ventas/page/<int:page>"],
                type="http", auth="user", website=True)
    def portal_my_ventas(self, page=1, sortby=None, filterby=None,
                         search=None, search_in="todo", **kw):
        Visita = request.env["atc.visita"]
        _ = request.env._
        searchbar_sortings = {
            "recientes": {"label": _("Más recientes primero"),
                          "order": "fecha_asignacion desc, id desc"},
            "antiguedad": {"label": _("Más antiguas primero"),
                           "order": "fecha_asignacion asc, id asc"},
            "cliente": {"label": _("Cliente"), "order": "nombre asc, id asc"},
        }
        searchbar_filters = {
            "todas": {"label": _("Todas"), "domain": []},
            "en_proceso": {"label": _("En proceso"),
                           "domain": [("estado", "in", ESTADOS_EN_PROCESO)]},
            "instaladas": {"label": _("Instaladas"),
                           "domain": [("estado", "in", ("realizada", "garantia"))]},
            "no_instaladas": {"label": _("No se pudieron instalar"),
                              "domain": [("estado", "=", "no_realizada")]},
        }
        searchbar_inputs = {
            "todo": {"input": "todo", "label": _("Cliente, cédula o dirección")},
        }
        sortby = sortby if sortby in searchbar_sortings else "recientes"
        filterby = filterby if filterby in searchbar_filters else "todas"

        domain = self._ventas_domain() + searchbar_filters[filterby]["domain"]
        if search:
            domain += ["|", "|", ("nombre", "ilike", search),
                       ("cedula", "ilike", search),
                       ("direccion", "ilike", search)]

        total = Visita.search_count(domain)
        pager = portal_pager(
            url="/my/ventas",
            url_args={"sortby": sortby, "filterby": filterby,
                      "search": search, "search_in": search_in},
            total=total, page=page, step=PASO)
        ventas = Visita.search(
            domain, order=searchbar_sortings[sortby]["order"],
            limit=PASO, offset=pager["offset"])
        request.session["my_ventas_history"] = ventas.ids[:100]

        values = self._prepare_portal_layout_values()
        values.update({
            "ventas": ventas.sudo(),
            "page_name": "ventas",
            "default_url": "/my/ventas",
            "pager": pager,
            "searchbar_sortings": searchbar_sortings,
            "sortby": sortby,
            "searchbar_filters": searchbar_filters,
            "filterby": filterby,
            "searchbar_inputs": searchbar_inputs,
            "search_in": search_in,
            "search": search,
        })
        return request.render("atc_visitas_tecnicas.portal_my_ventas", values)

    @http.route(["/my/ventas/<int:orden_id>"],
                type="http", auth="user", website=True)
    def portal_my_venta(self, orden_id, **kw):
        try:
            orden_sudo = self._document_check_access("atc.visita", orden_id)
            if orden_sudo.tipo_orden != "instalacion" \
                    or request.env.user not in orden_sudo.vendedor_id.user_ids:
                raise MissingError(request.env._("Esta venta no existe."))
        except (AccessError, MissingError):
            return request.redirect("/my/ventas")
        values = self._prepare_portal_layout_values()
        values.update({"orden": orden_sudo, "page_name": "venta"})
        # Anterior / siguiente de la lista (access_url es la del contratista)
        historial = request.session.get("my_ventas_history") or []
        if orden_id in historial:
            i = historial.index(orden_id)
            if i > 0:
                values["prev_record"] = "/my/ventas/%s" % historial[i - 1]
            if i < len(historial) - 1:
                values["next_record"] = "/my/ventas/%s" % historial[i + 1]
        return request.render("atc_visitas_tecnicas.portal_my_venta", values)
