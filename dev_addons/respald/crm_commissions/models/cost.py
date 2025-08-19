from odoo import fields, models, api

class SaleOrder(models.Model):
    _inherit = 'sale.order'
    
    total_cost = fields.Float(string='Total Cost', compute='_compute_total_cost', store=True)

    @api.depends('order_line.product_cost', 'order_line.product_uom_qty')
    def _compute_total_cost(self):
        for order in self:
            total_cost = sum(order.order_line.mapped(lambda line: line.product_cost * line.product_uom_qty))
            order.total_cost = total_cost
    def _update_total_cost(self):
        for order in self:
            total_cost = sum(order.order_line.mapped('product_cost'))
            order.total_cost = total_cost

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    product_cost = fields.Float(string='Product Cost', compute='_compute_product_cost', store=True, readonly=False)

    @api.depends('product_id', 'product_id.standard_price')
    def _compute_product_cost(self):
        for line in self:
            line.product_cost = line.product_id.standard_price if line.product_id else 0.0
            line.order_id._update_total_cost()
    
    def _update_total_cost(self):
        for order in self:
            total_cost = sum(order.order_line.mapped('product_cost'))
            order.total_cost = total_cost

class SaleOrderCommission(models.Model):
    _inherit = 'sale.order'

    account_commission_ids = fields.Many2one(
        string='Oportunidad',
        comodel_name='accounts.payable.crm',
        ondelete='restrict',
    )   
    
    opportunity_id = fields.Many2one(
        string='Oportunidad',
        comodel_name='crm.lead',
        ondelete='restrict',
    )
    commission = fields.Float(string='Commission', related='opportunity_id.commission', store=True)
    total_amount = fields.Float(string='Total Pagado', related='account_commission_ids.total_amount')
    
    amount_remaining = fields.Float(string='Ganancia Neta', compute='_compute_amount_remaining', store=True)

    @api.depends('amount_total', 'commission', 'total_cost')
    def _compute_amount_remaining(self):
        for order in self:
            order.amount_remaining = order.amount_total - order.commission - order.total_cost
