from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import datetime, timedelta


class CrmCampaignAnalysisWizard(models.TransientModel):
    _name = 'crm.campaign.analysis.wizard'
    _description = 'CRM Campaign Analysis Wizard'

    date_from = fields.Date(string='From Date', default=lambda self: fields.Date.context_today(self) - timedelta(days=30))
    date_to = fields.Date(string='To Date', default=fields.Date.context_today)
    
    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from and wizard.date_to and wizard.date_from > wizard.date_to:
                raise ValidationError("'From Date' cannot be greater than 'To Date'")
    
    def action_generate_report(self):
        self.ensure_one()
        
        # Convert dates to datetime with time boundaries
        date_from = datetime.combine(self.date_from, datetime.min.time()) if self.date_from else None
        date_to = datetime.combine(self.date_to, datetime.max.time()) if self.date_to else None
        
        # Force refresh the materialized view to ensure data is up-to-date
        self.env['crm.campaign.analysis.report'].refresh_materialized_view()
        
        # Prepare context for the view
        ctx = self.env.context.copy()
        ctx.update({
            'date_from': self.date_from,
            'date_to': self.date_to,
            # Add a timestamp to force view refresh
            'search_disable_custom_filters': True,
            'pivot_refresh_timestamp': fields.Datetime.now(),
            'pivot_measures': ['percentage'],
            'group_by': ['campaign_id', 'stage_id'],
        })
        
        # Construct domain for the pivot view based on date range
        domain = []
        if date_from:
            domain.append(('create_date', '>=', date_from))
        if date_to:
            domain.append(('create_date', '<=', date_to))
        
        # Return the pivot view action
        return {
            'name': 'Campaign Analysis',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.campaign.analysis.report',
            'view_mode': 'pivot,graph',
            'context': ctx,
            'target': 'main',
            'domain': domain,
            'flags': {'clear_breadcrumbs': True},
        }
        
    def action_export_report(self):
        self.ensure_one()
        
        # Convert dates to datetime with time boundaries
        date_from = datetime.combine(self.date_from, datetime.min.time()) if self.date_from else None
        date_to = datetime.combine(self.date_to, datetime.max.time()) if self.date_to else None
        
        # Get analysis data
        report_model = self.env['crm.campaign.analysis.report']
        data = report_model.get_campaign_stage_analysis(date_from, date_to)
        
        # Prepare context for the export wizard
        ctx = self.env.context.copy()
        ctx.update({
            'campaign_analysis_data': data,
            'date_from': self.date_from,
            'date_to': self.date_to,
        })
        
        # Open export wizard
        return {
            'name': 'Export Campaign Analysis',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.campaign.analysis.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }
