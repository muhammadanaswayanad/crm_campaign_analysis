from odoo import http
from odoo.http import request
from datetime import datetime, timedelta


class CampaignAnalysisController(http.Controller):
    @http.route('/crm/campaign/analysis', type='http', auth='user', website=True)
    def campaign_analysis(self, date_from=None, date_to=None, **kw):
        # Default dates if not provided (30 days ago to today)
        if not date_from:
            date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
        if not date_to:
            date_to = datetime.now().strftime('%Y-%m-%d')
            
        # Convert string dates to date objects
        try:
            date_from_dt = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d').date()
        except ValueError:
            # Handle invalid dates
            date_from_dt = (datetime.now() - timedelta(days=30)).date()
            date_to_dt = datetime.now().date()
            date_from = date_from_dt.strftime('%Y-%m-%d')
            date_to = date_to_dt.strftime('%Y-%m-%d')
        
        # Convert to datetime format for the analysis
        date_from_datetime = datetime.combine(date_from_dt, datetime.min.time())
        date_to_datetime = datetime.combine(date_to_dt, datetime.max.time())
        
        # Force refresh the materialized view
        request.env['crm.campaign.analysis.report'].sudo().refresh_materialized_view()
        
        # Get report data
        report_data = request.env['crm.campaign.analysis.report'].sudo().get_campaign_stage_analysis(
            date_from=date_from_datetime, 
            date_to=date_to_datetime
        )
        
        values = {
            'date_from': date_from_dt,
            'date_to': date_to_dt,
            'date_from_str': date_from,
            'date_to_str': date_to,
            'campaigns': list(report_data.get('campaigns', {}).keys()),
            'campaign_names': {campaign_id: report_data['campaigns'][campaign_id]['name'] 
                             for campaign_id in report_data.get('campaigns', {})},
            'stages': list(report_data.get('stages', {}).keys()),
            'stage_names': report_data.get('stages', {}),
            'campaign_data': {campaign_id: report_data['campaigns'][campaign_id] 
                             for campaign_id in report_data.get('campaigns', {})},
            'isinstance': isinstance,  # Needed for type checking in template
        }
        
        return request.render('crm_campaign_analysis.campaign_analysis_web_template', values)
