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
        # First drop the view if it exists (whether regular or materialized)
        self.env.cr.execute("DROP MATERIALIZED VIEW IF EXISTS %s CASCADE" % self._table)
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        # Create a materialized view for better performance
        self.env.cr.execute("""
            CREATE MATERIALIZED VIEW %s AS (
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
            ) WITH DATA
        """ % self._table)
        
        # Create indexes for better performance
        self.env.cr.execute("""
            CREATE UNIQUE INDEX %s_id_idx ON %s (id)
        """ % (self._table, self._table))
        
        self.env.cr.execute("""
            CREATE INDEX %s_campaign_idx ON %s (campaign_id)
        """ % (self._table, self._table))
        
        self.env.cr.execute("""
            CREATE INDEX %s_stage_idx ON %s (stage_id)
        """ % (self._table, self._table))

    @api.model
    def get_campaign_stage_analysis(self, date_from=None, date_to=None):
        """
        Get campaign analysis data with stage distribution
        :param date_from: optional filter for leads created from this date
        :param date_to: optional filter for leads created until this date
        :return: dict with campaign data and stage distribution
        """
        # Refresh the materialized view to get the most up-to-date data
        self._cr.execute("REFRESH MATERIALIZED VIEW %s" % self._table)
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
            
        # Get campaigns with leads in the time period and their total leads
        campaigns_query = """
            SELECT c.id, c.name, COUNT(l.id) AS total_leads
            FROM utm_campaign c
            JOIN crm_lead l ON l.campaign_id = c.id
            WHERE l.campaign_id IS NOT NULL
            AND c.active = True
            """ + date_condition + """
            GROUP BY c.id, c.name
            ORDER BY c.name
        """
        self.env.cr.execute(campaigns_query, params)
        campaigns_result = self.env.cr.dictfetchall()
        
        # Get stage counts per campaign
        counts_query = """
            SELECT l.campaign_id, l.stage_id, COUNT(l.id) AS lead_count
            FROM crm_lead l
            JOIN utm_campaign c ON c.id = l.campaign_id
            WHERE l.campaign_id IS NOT NULL
            AND c.active = True
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
        
        # Fill campaigns dictionary with basic data (only for campaigns with leads in the period)
        for campaign in campaigns_result:
            campaign_id = campaign['id']
            campaigns[campaign_id] = {
                'name': campaign['name'],
                'total_leads': campaign['total_leads'],
                'stages': {}
            }
        
        # Add stage counts and calculate percentage distribution per campaign
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

    @api.model
    def refresh_materialized_view(self):
        """
        Manually refresh the materialized view. 
        Can be called from a server action if needed.
        """
        self._cr.execute("REFRESH MATERIALIZED VIEW %s" % self._table)
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Refresh Complete',
                'message': 'The campaign analysis data has been refreshed.',
                'sticky': False,
            }
        }

    @api.model
    def search_read(self, domain=None, fields=None, offset=0, limit=None, order=None):
        # Check if we have date filters in context
        ctx = self.env.context
        date_from = ctx.get('date_from')
        date_to = ctx.get('date_to')
        
        # Get the refresh timestamp from context
        refresh_timestamp = ctx.get('pivot_refresh_timestamp')
        
        if date_from or date_to or refresh_timestamp:
            # Force a refresh of the materialized view before searching
            self.env.cr.execute("REFRESH MATERIALIZED VIEW %s" % self._table)
        
        # Continue with normal search_read
        return super(CrmCampaignAnalysisReport, self).search_read(domain, fields, offset, limit, order)
