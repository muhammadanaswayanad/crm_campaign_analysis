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
        
        # Get analysis data
        report_model = self.env['crm.campaign.analysis.report']
        data = report_model.get_campaign_stage_analysis(date_from, date_to)
        
        # Prepare context for the view
        ctx = self.env.context.copy()
        ctx.update({
            'campaign_analysis_data': data,
            'date_from': self.date_from,
            'date_to': self.date_to,
            # Add a timestamp to force view refresh
            'search_disable_custom_filters': True,
            'pivot_refresh_timestamp': fields.Datetime.now(),
            'pivot_measures': ['percentage'],
        })
        
        # Return the pivot view action instead of client action
        return {
            'name': 'Campaign Analysis',
            'type': 'ir.actions.act_window',
            'res_model': 'crm.campaign.analysis.report',
            'view_mode': 'pivot',
            'context': ctx,
            'target': 'main',
            'domain': [],
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
