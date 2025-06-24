from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from psycopg2 import sql
import datetime


class CrmCampaignAnalysisReport(models.Model):
    _name = 'crm.campaign.analysis.report'
    _description = 'CRM Campaign Analysis Report'
    _auto = False
    _rec_name = 'campaign_id'
    _order = 'campaign_id, create_date desc'

    campaign_id = fields.Many2one('utm.campaign', string='Campaign', readonly=True)
    stage_id = fields.Many2one('crm.stage', string='Stage', readonly=True)
    create_date = fields.Datetime(string='Created On', readonly=True)
    lead_count = fields.Integer(string='Lead Count', readonly=True)
    total_leads = fields.Integer(string='Total Campaign Leads', readonly=True)
    percentage = fields.Float(string='Percentage', readonly=True, group_operator="avg", digits=(16, 2))

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE or REPLACE VIEW %s AS (
                SELECT
                    row_number() OVER () AS id,
                    l.campaign_id,
                    l.stage_id,
                    l.create_date,
                    COUNT(l.id) AS lead_count,
                    camp_total.total_count AS total_leads,
                    (COUNT(l.id) * 100.0 / NULLIF(camp_total.total_count, 0)) AS percentage
                FROM
                    crm_lead l
                JOIN
                    (SELECT campaign_id, COUNT(id) AS total_count
                     FROM crm_lead
                     WHERE campaign_id IS NOT NULL
                     GROUP BY campaign_id) AS camp_total ON camp_total.campaign_id = l.campaign_id
                WHERE
                    l.campaign_id IS NOT NULL
                GROUP BY
                    l.campaign_id, l.stage_id, l.create_date, camp_total.total_count
            )
        """ % self._table)

    @api.model
    def get_campaign_stage_analysis(self, date_from=None, date_to=None):
        """
        Get campaign analysis data with stage distribution
        :param date_from: optional filter for leads created from this date
        :param date_to: optional filter for leads created until this date
        :return: dict with campaign data and stage distribution
        """
        # First, get all campaigns
        campaigns_query = """
            SELECT c.id, c.name 
            FROM utm_campaign c 
            ORDER BY c.name
        """
        self.env.cr.execute(campaigns_query)
        campaigns_result = self.env.cr.dictfetchall()
        
        # Get all stages
        stages_query = """
            SELECT s.id, s.name 
            FROM crm_stage s 
            ORDER BY s.sequence
        """
        self.env.cr.execute(stages_query)
        stages_result = self.env.cr.dictfetchall()
        
        # For each campaign, get the total leads count with date filter
        date_condition = ""
        params = []
        if date_from:
            date_condition += " AND l.create_date >= %s"
            params.append(date_from)
        if date_to:
            date_condition += " AND l.create_date <= %s"
            params.append(date_to)
            
        # Get total leads per campaign
        totals_query = """
            SELECT l.campaign_id, COUNT(l.id) AS total_leads
            FROM crm_lead l
            WHERE l.campaign_id IS NOT NULL
            """ + date_condition + """
            GROUP BY l.campaign_id
        """
        self.env.cr.execute(totals_query, params)
        totals_result = {r['campaign_id']: r['total_leads'] for r in self.env.cr.dictfetchall()}
        
        # Get stage counts per campaign
        counts_query = """
            SELECT l.campaign_id, l.stage_id, COUNT(l.id) AS lead_count
            FROM crm_lead l
            WHERE l.campaign_id IS NOT NULL
            """ + date_condition + """
            GROUP BY l.campaign_id, l.stage_id
        """
        self.env.cr.execute(counts_query, params)
        counts_result = self.env.cr.dictfetchall()
        
        # Organize the data
        campaigns = {}
        stages = {}
        
        # Fill stages dictionary
        for stage in stages_result:
            stages[stage['id']] = stage['name']
        
        # Fill campaigns dictionary with basic data
        for campaign in campaigns_result:
            campaign_id = campaign['id']
            if campaign_id in totals_result:
                campaigns[campaign_id] = {
                    'name': campaign['name'],
                    'total_leads': totals_result[campaign_id],
                    'stages': {}
                }
        
        # Add stage counts for each campaign
        for count in counts_result:
            campaign_id = count['campaign_id']
            stage_id = count['stage_id']
            if campaign_id in campaigns and stage_id in stages:
                lead_count = count['lead_count']
                total = campaigns[campaign_id]['total_leads']
                percentage = (lead_count * 100.0 / total) if total else 0.0
                
                campaigns[campaign_id]['stages'][stage_id] = {
                    'lead_count': lead_count,
                    'percentage': percentage
                }
                
        return {
            'campaigns': campaigns,
            'stages': stages
        }
