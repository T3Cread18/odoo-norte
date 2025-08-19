from datetime import datetime
from email.policy import default
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError

READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'sale', 'done', 'cancel','payment'}
}
class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    partner_phone = fields.Char(
        string='Phone',
        related='opportunity_id.phone',
        store=True,
    )
    partner_zip = fields.Char(
        string='Zip',
        related='opportunity_id.zip',
        store=True,
    )
    partner_city = fields.Char(
        string='City',
        related='opportunity_id.city',
        store=True,
    )
    partner_street= fields.Char(
        string='Street',
        related='opportunity_id.street',
        store=True,
    )
    partner_state = fields.Many2one(
        string='State',
        related='opportunity_id.state_id',
        store=True,
    )
    partner_country = fields.Many2one(
        string='Country',
        related='opportunity_id.country_id',
        store=True,
    )
    internal_description = fields.Html(
        string='Nota',
        related='opportunity_id.description',
        readonly=False
        )
    payment_details = fields.One2many(
        'account.payment.register.commission',
        'sale_order_id',
        string='Payment Details'
        )
    def action_confirm(self):
        # Llama al método original de action_confirm
        res = super(SaleOrder, self).action_confirm()

        # Archiva la oportunidad asociada después de confirmar el pedido
        self.opportunity_id.action_archive()

        return res

class SagitleOrderInherit(models.Model):
    _inherit = 'sale.order'

    READONLY_FIELD_STATES = {
    state: [('readonly', True)]
    for state in {'sale', 'done', 'cancel','payment'}
    }
    state = fields.Selection(
        selection=[
            ('draft', "Quotation"),
            ('sent', "Quotation Sent"),
            ('sale', "POR PAGAR"),
            ('done', "Locked"),
            ('cancel', "Cancelled"),
            ('payment', "Pagado"),
        ],
        string="Status",
        readonly=True, copy=False, index=True,
        tracking=3,
        default='draft')
     
    
    payment_sale_ids = fields.One2many('account.payment.register.commission', 'sale_order_id', string='payment_sale')
    total_payments = fields.Float(
        string='Total Pagados' ,compute="_compute_total_payments"   )
    
    def _compute_total_payments (self):
        for rec in self: 
            objeto_payments = self.env['account.payment.register.commission'].search([('sale_order_id', '=', rec.id)])
            total_pagado  = sum(map(lambda p: p.amount, objeto_payments))

            rec.sudo().write({
                    'total_payments':total_pagado if total_pagado else 0.0
                })
            if total_pagado >= rec.amount_total:
                rec.sudo().write({'state':'payment'})

    def create_payment_sale(self):
        objeto_payments = self.env['account.payment.register.commission'].search([('sale_order_id', '=', self.id)])
        total_pagado  = sum(map(lambda p: p.amount, objeto_payments))
        if total_pagado >= self.amount_total:
            self.state= 'payment'
        else:
            return {
                'name': _('Registar Pago de Venta'),
                'res_model': 'account.payment.register.commission',
                'view_mode': 'form',
                'context': {
                    'default_sale_order_id': self.id,
                    'default_catidad': self.amount_total,
                    'default_communication': self.display_name,
                    'default_is_payment_sale':True
                },
                'target': 'new',
                'type': 'ir.actions.act_window',
            }
    faltan_cobrar = fields.Float(
        string='Faltan',
        compute='_compute_amount_faltan',
        store=True
        )
    @api.depends('faltan_cobrar', 'total_payments', 'amount_total')
    def _compute_amount_faltan(self):
        for order in self:
            order.faltan_cobrar = order.amount_total - order.total_payments

    def action_preview_commission(self):
        if not self.opportunity_id:
            raise UserError('No hay una oportunidad asociada a esta orden de venta.')
        
        commission = self.env['accounts.payable.crm'].search([('oprtunity_id', '=', self.opportunity_id.id)])
        if not commission:
            raise UserError('No se encontró una comisión asociada a esta oportunidad.')
        
        # Aquí abrimos la vista previa de la comisión
        return {
            'type': 'ir.actions.act_window',
            'name': 'Vista previa de comisión',
            'res_model': 'accounts.payable.crm',
            'res_id': commission.id,
            'view_mode': 'form',
            'target': 'new',
        }
        
    first_order_line_name = fields.Char(
        string='First Order Line Name',
        compute='_compute_first_order_line_name'
    )

    @api.depends('order_line')
    def _compute_first_order_line_name(self):
        for order in self:
            if order.order_line:
                order.first_order_line_name = order.order_line[0].name
            else:
                order.first_order_line_name = ''