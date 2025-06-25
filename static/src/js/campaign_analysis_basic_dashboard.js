odoo.define('crm_campaign_analysis.basic_dashboard', function (require) {
    "use strict";

    var core = require('web.core');
    var Widget = require('web.Widget');
    var AbstractAction = require('web.AbstractAction');
    var rpc = require('web.rpc');

    var CampaignAnalysisBasicDashboard = AbstractAction.extend({
        template: 'CampaignAnalysisBasicDashboard',

        init: function(parent, action) {
            this._super.apply(this, arguments);
            this.action = action;
            this.context = action.context || {};
        },

        start: function() {
            var self = this;
            return this._super.apply(this, arguments).then(function() {
                return self._renderView();
            });
        },

        _renderView: function() {
            var self = this;
            return rpc.query({
                model: 'crm.campaign.analysis.report',
                method: 'get_campaign_stage_analysis',
                args: [
                    this.context.date_from || false, 
                    this.context.date_to || false
                ],
                context: this.context,
            }).then(function(data) {
                if (!data || !data.campaigns || Object.keys(data.campaigns).length === 0) {
                    self.$el.html('<div class="alert alert-info">No data available for the selected date range.</div>');
                    return;
                }

                var $table = $('<table class="table table-bordered table-striped">');
                var $thead = $('<thead>');
                var $headerRow = $('<tr>');
                
                $headerRow.append($('<th>').text('Campaign'));
                
                // Add stage headers
                for (var stageId in data.stages) {
                    var stageName = data.stages[stageId];
                    if (typeof stageName === 'object' && stageName !== null) {
                        // If it's a translation dict, get the first value
                        stageName = Object.values(stageName)[0] || 'Unknown';
                    }
                    $headerRow.append($('<th>').text(stageName + ' (%)'));
                }
                
                $headerRow.append($('<th>').text('Total Leads'));
                $thead.append($headerRow);
                $table.append($thead);
                
                var $tbody = $('<tbody>');
                
                // Add campaign data rows
                for (var campaignId in data.campaigns) {
                    var campaign = data.campaigns[campaignId];
                    var $row = $('<tr>');
                    
                    $row.append($('<td>').text(campaign.name));
                    
                    // Add stage percentages
                    for (var stageId in data.stages) {
                        var stageInfo = campaign.stages[stageId] || {percentage: 0.0};
                        var $cell = $('<td>').text(stageInfo.percentage.toFixed(2) + '%');
                        
                        // Apply highlighting
                        var stageName = String(data.stages[stageId] || '').toUpperCase();
                        if (typeof data.stages[stageId] === 'object') {
                            stageName = String(Object.values(data.stages[stageId])[0] || '').toUpperCase();
                        }
                        
                        if ((stageName.includes('JUNK') && stageInfo.percentage > 20) ||
                            ((stageName.includes('NOT CONNECTED') || stageName === 'NC') && stageInfo.percentage > 20) ||
                            ((stageName.includes('ADMISSION') || stageName === 'A') && stageInfo.percentage < 5) ||
                            ((stageName.includes('HOT PROSPECT') || stageName === 'HP' || 
                              stageName.includes('FUTURE PROSPECT') || stageName === 'FP')) && stageInfo.percentage < 5) {
                            $cell.css('background-color', '#ffcccb').css('color', '#721c24');
                        }
                        
                        $row.append($cell);
                    }
                    
                    $row.append($('<td>').text(campaign.total_leads));
                    $tbody.append($row);
                }
                
                $table.append($tbody);
                self.$el.html($table);
                
                // Add highlighting legend
                var $legend = $('<div class="mt-3">').append(
                    $('<h5>').text('Highlighting Rules:'),
                    $('<ul>').append(
                        $('<li>').text('Red: JUNK > 20%'),
                        $('<li>').text('Red: Not Connected (NC) > 20%'),
                        $('<li>').text('Red: Admission (A) < 5%'),
                        $('<li>').text('Red: Hot Prospect (HP) or Future Prospect (FP) < 5%')
                    )
                );
                
                self.$el.append($legend);
            });
        }
    });

    // Register the client action
    core.action_registry.add('campaign_analysis_dashboard', CampaignAnalysisBasicDashboard);

    return CampaignAnalysisBasicDashboard;
});
