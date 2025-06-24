{
    'name': 'CRM Campaign Analysis',
    'version': '17.0.1.0.0',
    'summary': 'Campaign Analysis Report for CRM',
    'description': '''
        This module adds a campaign analysis report for CRM leads,
        showing distribution of leads across stages per campaign.
    ''',
    'category': 'CRM',
    'author': 'Odoo',
    'website': 'https://www.odoo.com',
    'depends': ['crm'],
    'data': [
        'security/ir.model.access.csv',
        'report/crm_campaign_analysis_report_view.xml',
        'report/export_wizard_view.xml',
        'report/report_campaign_analysis_template.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
