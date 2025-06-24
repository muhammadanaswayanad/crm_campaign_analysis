from odoo import models, fields, api
import base64
import io
import csv
import xlsxwriter


class ReportExportWizard(models.TransientModel):
    _name = 'crm.campaign.analysis.export.wizard'
    _description = 'Export Campaign Analysis'

    export_type = fields.Selection([
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF')
    ], string='Export Type', default='xlsx', required=True)
    
    data = fields.Binary('File', readonly=True)
    filename = fields.Char('Filename', readonly=True)
    state = fields.Selection([
        ('choose', 'choose'),
        ('done', 'done')
    ], string='State', default='choose')
    
    def action_export(self):
        self.ensure_one()
        
        # Get context information passed from the wizard
        ctx = self.env.context
        date_from = ctx.get('date_from')
        date_to = ctx.get('date_to')
        
        # Get report data
        report_model = self.env['crm.campaign.analysis.report']
        data = report_model.get_campaign_stage_analysis(date_from, date_to)
        
        if self.export_type == 'csv':
            return self._export_csv(data)
        elif self.export_type == 'xlsx':
            return self._export_xlsx(data)
        elif self.export_type == 'pdf':
            return self._export_pdf(data)
            
    def _export_csv(self, data):
        # Initialize string IO and csv writer
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write headers
        headers = ['Campaign']
        for stage_id, stage_name in data.get('stages', {}).items():
            headers.append(f"{stage_name} (%)")
        headers.append('Total Leads')
        writer.writerow(headers)
        
        # Write data rows
        for campaign_id, campaign_data in data.get('campaigns', {}).items():
            row = [campaign_data['name']]
            for stage_id, stage_name in data.get('stages', {}).items():
                stage_info = campaign_data['stages'].get(stage_id, {'percentage': 0.0, 'lead_count': 0})
                row.append(f"{stage_info['percentage']:.2f}%")
            row.append(campaign_data['total_leads'])
            writer.writerow(row)
            
        # Set file name and data
        filename = f'campaign_analysis_{fields.Date.today().strftime("%Y%m%d")}.csv'
        self.write({
            'data': base64.b64encode(output.getvalue().encode('utf-8')),
            'filename': filename,
            'state': 'done'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
        
    def _export_xlsx(self, data):
        # Create a new workbook and worksheet
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Campaign Analysis')
        
        # Define styles
        header_format = workbook.add_format({
            'bold': True,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#D3D3D3',
            'border': 1
        })
        
        percentage_format = workbook.add_format({
            'num_format': '0.00%',
            'border': 1
        })
        
        number_format = workbook.add_format({
            'num_format': '#,##0',
            'border': 1
        })
        
        text_format = workbook.add_format({
            'border': 1
        })
        
        # Write headers
        worksheet.write(0, 0, 'Campaign', header_format)
        col = 1
        
        # Write stage headers
        for stage_id, stage_name in data.get('stages', {}).items():
            worksheet.write(0, col, f"{stage_name} (%)", header_format)
            col += 1
            
        worksheet.write(0, col, 'Total Leads', header_format)
        
        # Write data rows
        row = 1
        for campaign_id, campaign_data in data.get('campaigns', {}).items():
            worksheet.write(row, 0, campaign_data['name'], text_format)
            col = 1
            
            for stage_id, stage_name in data.get('stages', {}).items():
                stage_info = campaign_data['stages'].get(stage_id, {'percentage': 0.0, 'lead_count': 0})
                worksheet.write(row, col, stage_info['percentage'] / 100, percentage_format)
                col += 1
                
            worksheet.write(row, col, campaign_data['total_leads'], number_format)
            row += 1
        
        # Adjust column widths
        worksheet.set_column(0, 0, 30)
        worksheet.set_column(1, col, 15)
        
        # Close workbook
        workbook.close()
        
        # Set file name and data
        filename = f'campaign_analysis_{fields.Date.today().strftime("%Y%m%d")}.xlsx'
        self.write({
            'data': base64.b64encode(output.getvalue()),
            'filename': filename,
            'state': 'done'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
        
    def _export_pdf(self, data):
        # For PDF, we'll use Odoo's report system
        # Set context to include data for report template
        ctx = dict(self.env.context)
        ctx.update({
            'campaign_analysis_data': data,
            'date_from': ctx.get('date_from'),
            'date_to': ctx.get('date_to'),
        })
        
        report = self.env.ref('crm_campaign_analysis.action_report_campaign_analysis')
        pdf = report.with_context(ctx)._render_qweb_pdf(self.ids)[0]
        
        # Set file name and data
        filename = f'campaign_analysis_{fields.Date.today().strftime("%Y%m%d")}.pdf'
        self.write({
            'data': base64.b64encode(pdf),
            'filename': filename,
            'state': 'done'
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
            'context': self.env.context,
        }
