from odoo import api, fields, models, tools
from odoo.exceptions import UserError
from psycopg2 import sql
import datetime
import logging

_logger = logging.getLogger(__name__)

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
        # First check if the table exists
        self.env.cr.execute("SELECT to_regclass(%s)", (self._table,))
        exists = self.env.cr.fetchone()[0]
        
        # Handle the case where it might be a regular view first
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        # Now try to drop it if it's a materialized view (should only happen on re-install)
        try:
            self.env.cr.execute("DROP MATERIALIZED VIEW IF EXISTS %s CASCADE" % self._table)
        except Exception:
            # If this fails, it's ok - the view doesn't exist or is already dropped
            pass
            
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
        
        # Create indexes for better performance - using IF NOT EXISTS to be safe
        try:
            self.env.cr.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS %s_id_idx ON %s (id)
            """ % (self._table, self._table))
            
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS %s_campaign_idx ON %s (campaign_id)
            """ % (self._table, self._table))
            
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS %s_stage_idx ON %s (stage_id)
            """ % (self._table, self._table))
        except Exception as e:
            # Log the error but continue - indexes are optional
            _logger.warning("Failed to create indexes on %s: %s", self._table, str(e))

    @api.model
    def get_campaign_stage_analysis(self, date_from=None, date_to=None):
        """
        Get campaign analysis data with stage distribution
        :param date_from: optional filter for leads created from this date
        :param date_to: optional filter for leads created until this date
        :return: dict with campaign data and stage distribution
        """
        # Refresh the materialized view to get the most up-to-date data
        try:
            self._cr.execute("REFRESH MATERIALIZED VIEW %s" % self._table)
        except Exception as e:
            _logger.warning("Failed to refresh materialized view: %s", str(e))
            
        # Get all stages - use orm instead of raw query to handle translations properly
        stages = self.env['crm.stage'].search([], order='sequence')
        stages_result = []
        for stage in stages:
            # Get the user's language-specific name by accessing the display_name
            stages_result.append({
                'id': stage.id,
                'name': stage.display_name or stage.name  # Use display_name or fallback to name
            })
        
        # For each campaign, get the total leads count with date filter
        date_condition = ""
        params = []
        if date_from:
            date_condition += " AND l.create_date >= %s"
            params.append(date_from)
        if date_to:
            date_condition += " AND l.create_date <= %s"
            params.append(date_to)
            
        # Use a direct query to get the stage distributions accurately
        # We will get lead counts per stage per campaign
        stage_distribution_query = """
            WITH campaign_leads AS (
                SELECT 
                    c.id AS campaign_id,
                    c.name AS campaign_name,
                    l.stage_id,
                    COUNT(l.id) AS lead_count
                FROM utm_campaign c
                JOIN crm_lead l ON l.campaign_id = c.id
                WHERE c.active = True
                AND l.active = True
                """ + date_condition + """
                GROUP BY c.id, c.name, l.stage_id
            ),
            campaign_totals AS (
                SELECT 
                    campaign_id,
                    campaign_name,
                    SUM(lead_count) AS total_leads
                FROM campaign_leads
                GROUP BY campaign_id, campaign_name
            )
            SELECT 
                cl.campaign_id,
                ct.campaign_name,
                cl.stage_id,
                cl.lead_count,
                ct.total_leads,
                (cl.lead_count * 100.0 / ct.total_leads) AS percentage
            FROM campaign_leads cl
            JOIN campaign_totals ct ON cl.campaign_id = ct.campaign_id
            ORDER BY ct.campaign_name, cl.stage_id
        """
        self.env.cr.execute(stage_distribution_query, params)
        stage_results = self.env.cr.dictfetchall()
        
        # Get campaign totals
        campaign_totals_query = """
            SELECT 
                c.id AS campaign_id,
                c.name AS campaign_name,
                COUNT(l.id) AS total_leads
            FROM utm_campaign c
            JOIN crm_lead l ON l.campaign_id = c.id
            WHERE c.active = True
            AND l.active = True
            """ + date_condition + """
            GROUP BY c.id, c.name
            ORDER BY c.name
        """
        self.env.cr.execute(campaign_totals_query, params)
        campaigns_result = self.env.cr.dictfetchall()
        
        # Organize the data
        campaigns = {}
        stages = {}
        
        # Fill stages dictionary
        for stage in stages_result:
            stages[stage['id']] = stage['name']
        
        # Fill campaigns dictionary with basic data
        for campaign in campaigns_result:
            campaign_id = campaign['campaign_id']
            campaigns[campaign_id] = {
                'name': campaign['campaign_name'],
                'total_leads': campaign['total_leads'],
                'stages': {}
            }
        
        # Add stage counts and percentages
        for result in stage_results:
            campaign_id = result['campaign_id']
            stage_id = result['stage_id']
            if campaign_id in campaigns and stage_id in stages:
                lead_count = result['lead_count']
                total = result['total_leads']
                percentage = result['percentage']
                
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
        try:
            self._cr.execute("REFRESH MATERIALIZED VIEW %s" % self._table)
            message = 'The campaign analysis data has been refreshed.'
            title = 'Refresh Complete'
        except Exception as e:
            message = f'Failed to refresh data: {str(e)}'
            title = 'Refresh Failed'
            _logger.error("Failed to refresh materialized view: %s", str(e))
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': title,
                'message': message,
                'sticky': title == 'Refresh Failed',
                'type': 'success' if title == 'Refresh Complete' else 'danger',
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
            try:
                # Force a refresh of the materialized view before searching
                self._cr.execute("REFRESH MATERIALIZED VIEW %s" % self._table)
            except Exception as e:
                _logger.warning("Failed to refresh materialized view: %s", str(e))
        
        # Continue with normal search_read
        return super(CrmCampaignAnalysisReport, self).search_read(domain, fields, offset, limit, order)
