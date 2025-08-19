from datetime import datetime
from email.policy import default
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class CrmLeadIherit(models.Model):
    _inherit = 'crm.lead'

    commission = fields.Float('Comisión', tracking=True)


    accounts_payable_crm_ids = fields.One2many(
        string='Cuentas por pagar',
        comodel_name='accounts.payable.crm',
        inverse_name='oprtunity_id',
    )
    cost_ids = fields.One2many(
        string='comis por pagar',
        comodel_name='sale.order',
        inverse_name='opportunity_id',
    )
    company_id = fields.Many2one(
        string='Company', 
        comodel_name='res.company', 
        required=True, 
        default=lambda self: self.env.user.company_id
    )

    fecha_mes = fields.Char(string='Mes', readonly=True, store=False, compute='_compute_fecha_mes')

    state = fields.Selection(
        string='state',
        selection=[('borrador', 'Borrador'), ('confirmado', 'confirmado')],
        default='borrador',
    )
    
    


    def confirmar_aoportunity (self):
        for rec in self:
            if rec.commission > -1 and  rec.commission < rec.expected_revenue:
                rec.state='confirmado'
                self.register_account_payable()


    def register_account_payable(self):
        x = self.env['accounts.payable.crm'].sudo().create({'oprtunity_id' : self.id,
                                                            'contact_name' : self.name,
                                                            'user_id' : self.user_id.id})
        
    def _compute_fecha_mes(self):
        for record in self:
            if record.create_date:
                record.fecha_mes = record.create_date.strftime('%B')  # %B representa el nombre completo del mes
            else:
                record.fecha_mes = False  # Opcional: Si no hay fecha, puedes establecer un valor predeterminado
    @api.onchange('user_id')
    def _onchange_user_id(self):
        if self.user_id:
            self.contact_name = self.user_id.name
        else:
            self.contact_name = ''