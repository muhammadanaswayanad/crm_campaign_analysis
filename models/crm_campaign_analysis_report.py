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
        where_clause = []
        params = []

        if date_from:
            where_clause.append("l.create_date >= %s")
            params.append(date_from)
        if date_to:
            where_clause.append("l.create_date <= %s")
            params.append(date_to)

        where_str = " AND ".join(where_clause)
        where_sql = sql.SQL("")
        if where_str:
            where_sql = sql.SQL("AND ") + sql.SQL(where_str)

        query = sql.SQL("""
            WITH campaign_totals AS (
                SELECT
                    l.campaign_id,
                    COUNT(l.id) AS total_leads
                FROM
                    crm_lead l
                WHERE
                    l.campaign_id IS NOT NULL
                    {where_clause}
                GROUP BY
                    l.campaign_id
            ),
            campaign_stage_counts AS (
                SELECT
                    l.campaign_id,
                    l.stage_id,
                    COUNT(l.id) AS stage_count
                FROM
                    crm_lead l
                WHERE
                    l.campaign_id IS NOT NULL
                    {where_clause}
                GROUP BY
                    l.campaign_id, l.stage_id
            )
            SELECT
                c.id AS campaign_id,
                c.name AS campaign_name,
                s.id AS stage_id,
                s.name AS stage_name,
                COALESCE(csc.stage_count, 0) AS lead_count,
                ct.total_leads,
                (COALESCE(csc.stage_count, 0) * 100.0 / NULLIF(ct.total_leads, 0)) AS percentage
            FROM
                utm_campaign c
            CROSS JOIN
                crm_stage s
            JOIN
                campaign_totals ct ON ct.campaign_id = c.id
            LEFT JOIN
                campaign_stage_counts csc ON csc.campaign_id = c.id AND csc.stage_id = s.id
            ORDER BY
                c.name, s.sequence
        """).format(where_clause=where_sql)

        self.env.cr.execute(query, params)
        results = self.env.cr.dictfetchall()

        # Organize data by campaign
        campaigns = {}
        stages = {}
        
        for row in results:
            campaign_id = row['campaign_id']
            stage_id = row['stage_id']
            
            if stage_id not in stages:
                stages[stage_id] = row['stage_name']
                
            if campaign_id not in campaigns:
                campaigns[campaign_id] = {
                    'name': row['campaign_name'],
                    'total_leads': row['total_leads'],
                    'stages': {}
                }
                
            campaigns[campaign_id]['stages'][stage_id] = {
                'lead_count': row['lead_count'],
                'percentage': row['percentage'] or 0.0
            }

        return {
            'campaigns': campaigns,
            'stages': stages
        }
