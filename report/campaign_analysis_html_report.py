from odoo import models, fields, api
from datetime import datetime


class CampaignAnalysisHTMLReport(models.AbstractModel):
    _name = 'report.crm_campaign_analysis.campaign_analysis_report_template'
    _description = 'Campaign Analysis HTML Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Prepare data for the HTML report template"""
        # Get the date range from context or data
        ctx = self.env.context
        date_from = ctx.get('date_from') or (data and data.get('date_from'))
        date_to = ctx.get('date_to') or (data and data.get('date_to'))
        
        # Convert dates to datetime with time boundaries if they're not already
        if date_from and not isinstance(date_from, datetime):
            date_from = datetime.combine(date_from, datetime.min.time())
        if date_to and not isinstance(date_to, datetime):
            date_to = datetime.combine(date_to, datetime.max.time())
            
        # Get the report data
        report_model = self.env['crm.campaign.analysis.report']
        data_dict = report_model.get_campaign_stage_analysis(date_from, date_to)
        
        # Extract campaigns and stages for the template
        campaigns = list(data_dict.get('campaigns', {}).keys())
        campaign_names = {campaign_id: data_dict['campaigns'][campaign_id]['name'] 
                         for campaign_id in campaigns}
        
        # Prepare stage data
        stages = list(data_dict.get('stages', {}).keys())
        stage_names = data_dict.get('stages', {})
        
        # Prepare campaign data in a format easier to use in the template
        campaign_data = {}
        for campaign_id in campaigns:
            campaign_data[campaign_id] = {
                'total_leads': data_dict['campaigns'][campaign_id]['total_leads'],
            }
            # Add percentages for each stage
            for stage_id in stages:
                stage_info = data_dict['campaigns'][campaign_id]['stages'].get(stage_id, {})
                campaign_data[campaign_id][stage_id] = stage_info
        
        return {
            'date_from': date_from,
            'date_to': date_to,
            'campaigns': campaigns,
            'stages': stages,
            'campaign_names': campaign_names,
            'stage_names': stage_names,
            'campaign_data': campaign_data,
            'isinstance': isinstance,  # Needed for type checking in template
        }
