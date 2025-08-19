import logging
from datetime import datetime
from email.policy import default
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

class AccountsPayableCrm(models.Model):
    _name = 'accounts.payable.crm'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin', 'utm.mixin']
    
    oprtunity_id = fields.Many2one(
        string='Oportunidad',
        comodel_name='crm.lead',
        ondelete='restrict',
    )

    commission_ids = fields.One2many(
        string='Cuentas por pagar',
        comodel_name='sale.order',
        inverse_name='account_commission_ids',
    )

    faltan = fields.Float(
        string= 'Faltan',
        compute = '_compute_total_faltan',
        group_operator='sum',
        store=True
    )
    contact_name = fields.Char(
        string='Nombre del Contacto',
        related='oprtunity_id.contact_name'
    )

    total_amount = fields.Float(
        string='Total Pagado',
        compute = '_compute_total_amount',
    )
    total_amounts = fields.Float(
        string='Total Pagados',
        compute = '_compute_total_amounts',
        store=True
    )
    commission = fields.Float(
        string="Comision",
        related='oprtunity_id.commission',
        store=True
    )
    
    company_currency = fields.Many2one("res.currency", string='Currency',compute_sudo=True, compute="_compute_company_currency" )
    
    company_id = fields.Many2one(
        string='Company', 
        comodel_name='res.company', 
        default=lambda self: self.env.user.company_id
    )
    
    state = fields.Selection(
        string='Estatus',
        selection=[('no_payment', 'No Pagado'),('in_process', 'En Proceso'), ('payment', 'Pagado')],
        default="no_payment"
    )
    
    user_id = fields.Many2one(
        string='Usuario',
        comodel_name='res.users',
        ondelete='restrict',
    )
    


    
    account_payment_commission_ids = fields.One2many('account.payment.register.commission', 'accounts_payable_crm_id', string='Pagos de comicion')
    
    # order_ids = fields.One2many(
    #     related='oprtunity_id.order_ids'
    # )

    def action_register_payment_crm(self):
        ''' Open the account.payment.register wizard to pay the selected journal entries.
        :return: An action opening the account.payment.register wizard.
        '''
        # object = self.env['account.payment.register.commission'].search([('accounts_payable_crm_id','=', self.id)])
        if self.total_amount >= self.commission:

            raise ValidationError("No puedes realizar mas pagos a esta comisión")


        return {
            'name': _('Registar Pago Comision'),
            'res_model': 'account.payment.register.commission',
            'view_mode': 'form',
            'context': {
                'default_accounts_payable_crm_id': self.id
            },
            'target': 'new',
            'type': 'ir.actions.act_window',
        }
    @api.depends('commission', 'total_amount')
    def _compute_total_faltan(self):
        for order in self:
            order.faltan = order.commission - order.total_amount
    @api.depends('faltan', 'commission')
    def _compute_total_amounts(self):
        for order in self:
            order.total_amounts = order.commission - order.faltan
    @api.depends('account_payment_commission_ids.amount')
    def _compute_total_amount(self):
        for rec in self:
            total_importe = sum(rec.account_payment_commission_ids.mapped('amount'))
            rec.total_amount = total_importe
            _logger.info('Computed total_amount for record %s: %s', rec.id, rec.total_amount)

            if rec.total_amount >= rec.commission:
                rec.state = 'payment'
            elif 0 < rec.total_amount < rec.commission:
                rec.state = 'in_process'
            else:
                rec.state = 'no_payment'
           
    def _compute_currency_id(self):
        for rec in self:
            rec.sudo().write({
            'currency_id': self.env.company.currency_id.id 
            }) 

    @api.depends('company_id')
    def _compute_company_currency(self):
        for rec in self:
            if not rec.company_id:
                rec.company_currency = rec.env.company.currency_id
            else:
                rec.company_currency = rec.company_id.currency_id
