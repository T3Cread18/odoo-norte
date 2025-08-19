from datetime import datetime
from email.policy import default
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class AccountsPaymenteRegisterCrm(models.Model):
    _name = 'account.payment.register.commission'

    accounts_payable_crm_id = fields.Many2one(
        string='Cuenta por Pagar',
        comodel_name='accounts.payable.crm',
        ondelete='restrict',
    )


    company_id = fields.Many2one(
        string='Company', 
        comodel_name='res.company', 
        required=True, 
        default=lambda self: self.env.user.company_id
    )
    company_currency = fields.Many2one("res.currency", string='Currency',compute_sudo=True, compute="_compute_company_currency" )
    catidad = fields.Float(
        string='Catidad a Pagar',
    )
    sale_order = fields.Many2one('sale.order', string='Sale Order')
    amount = fields.Float(
        string='Importe',
        store=True
    )
    
    payment_date = fields.Date(
        string='Fecha de Pago',
        default=fields.Date.context_today,
    )
    
    
    communication = fields.Char(
        string='Memo',
        # compute de name de oportunity
    )
    
    payment_method_line_id = fields.Many2one(
        string='Metodo de Pago',
        comodel_name='account.payment.method.line',
        ondelete='restrict',
    )


    
    sale_order_id = fields.Many2one(
        string='Orden de Venta',
        comodel_name='sale.order',
        ondelete='restrict',
    )
    
    name = fields.Char(
        string='name' , readonly=True)
    
    
    is_payment_sale = fields.Boolean(
        string='Pago de Venta',
        default="False"
    )
    
    @api.onchange('accounts_payable_crm_id','sale_order_id')
    def _onchange_importe_total(self):
        if self.accounts_payable_crm_id:
            object = self.env['account.payment.register.commission'].search([('accounts_payable_crm_id','=', self.accounts_payable_crm_id.id)])
            total_importe = sum(map(lambda p: p.amount, object))
            self.catidad = (self.accounts_payable_crm_id.commission - total_importe) if total_importe else self.accounts_payable_crm_id.commission
        elif self.sale_order_id :
            object = self.env['sale.order'].search([('id','=', self.sale_order_id.id)])
            payment = self.env['account.payment.register.commission'].search([('sale_order_id','=', object.id)])
            total_importe_pagado = sum(map(lambda p: p.amount, payment))
            total_importe = sum(map(lambda p: p.amount_total, object))
            
            self.catidad = (total_importe- total_importe_pagado ) if total_importe_pagado else total_importe
    
    
    
    @api.depends('company_id')
    def _compute_company_currency(self):
        for rec in self:
            if not rec.company_id:
                rec.company_currency = rec.env.company.currency_id
            else:
                rec.company_currency = rec.company_id.currency_id
    
    @api.model
    def create(self, vals):
        """Create Sequence"""
        sequence_code = "payment.sale.order"
        sequence_code_commission = "payment.commission"

        if  vals["is_payment_sale"] == True:
            vals["name"] = self.env["ir.sequence"].next_by_code(sequence_code)
            return super(AccountsPaymenteRegisterCrm, self).create(vals)            
        else:

            vals["name"] = self.env["ir.sequence"].next_by_code(sequence_code_commission)
            return super(AccountsPaymenteRegisterCrm, self).create(vals)

    