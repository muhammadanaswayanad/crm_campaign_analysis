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
            # Handle potential dictionary format from translation
            if isinstance(stage_name, dict):
                # Use the first value in the dict or a default value if empty
                name_value = next(iter(stage_name.values()), "Unknown")
            else:
                name_value = stage_name
                
            headers.append(f"{name_value} (%)")
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
        
        # Define red highlight format for warning conditions
        red_percentage_format = workbook.add_format({
            'num_format': '0.00%',
            'border': 1,
            'bg_color': '#FF9999',  # Light red background
            'color': '#990000'      # Dark red text
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
        
        # Write stage headers - ensure we're using string values for stage names
        for stage_id, stage_name in data.get('stages', {}).items():
            # Handle potential dictionary format from translation
            if isinstance(stage_name, dict):
                # Use the first value in the dict or a default value if empty
                name_value = next(iter(stage_name.values()), "Unknown")
            else:
                name_value = stage_name
                
            worksheet.write(0, col, f"{name_value} (%)", header_format)
            col += 1
            
        worksheet.write(0, col, 'Total Leads', header_format)
        
        # Write data rows
        row = 1
        for campaign_id, campaign_data in data.get('campaigns', {}).items():
            worksheet.write(row, 0, campaign_data['name'], text_format)
            col = 1
            
            for stage_id, stage_name in data.get('stages', {}).items():
                stage_info = campaign_data['stages'].get(stage_id, {'percentage': 0.0, 'lead_count': 0})
                percentage_value = stage_info['percentage'] / 100
                
                # Get clean stage name for condition checking
                if isinstance(stage_name, dict):
                    name_value = next(iter(stage_name.values()), "Unknown")
                else:
                    name_value = stage_name
                
                # Apply conditional formatting based on rules
                use_red_format = False
                
                # Condition 1: Highlight JUNK > 20%
                if "JUNK" in name_value and percentage_value > 0.2:
                    use_red_format = True
                
                # Condition 2: Highlight Not Connected (NC) > 20%
                if ("Not Connected" in name_value or "NC" in name_value) and percentage_value > 0.2:
                    use_red_format = True
                
                # Condition 3: Highlight Admission (A) < 5%
                if ("Admission" in name_value or name_value == "A") and percentage_value < 0.05:
                    use_red_format = True
                
                # Condition 4: Highlight Hot Prospect (HP) and Future Prospect (FP) < 5%
                if ("Hot Prospect" in name_value or name_value == "HP" or 
                    "Future Prospect" in name_value or name_value == "FP") and percentage_value < 0.05:
                    use_red_format = True
                
                # Write cell with appropriate format
                cell_format = red_percentage_format if use_red_format else percentage_format
                worksheet.write(row, col, percentage_value, cell_format)
                col += 1
                
            worksheet.write(row, col, campaign_data['total_leads'], number_format)
            row += 1
        
        # Adjust column widths
        worksheet.set_column(0, 0, 30)
        worksheet.set_column(1, col, 15)
        
        # Add a legend for the highlighting
        legend_row = row + 3
        legend_title_format = workbook.add_format({'bold': True})
        worksheet.write(legend_row, 0, "Highlighted Conditions (Red):", legend_title_format)
        worksheet.write(legend_row + 1, 0, "• JUNK > 20%")
        worksheet.write(legend_row + 2, 0, "• Not Connected (NC) > 20%")
        worksheet.write(legend_row + 3, 0, "• Admission (A) < 5%")
        worksheet.write(legend_row + 4, 0, "• Hot Prospect (HP) and Future Prospect (FP) < 5%")
        
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
