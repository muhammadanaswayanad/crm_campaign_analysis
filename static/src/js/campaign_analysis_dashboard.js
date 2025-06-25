odoo.define('crm_campaign_analysis.campaign_analysis_dashboard', ['web.core', 'web.Widget', 'web.rpc', 'web.AbstractAction', 'web.field_utils'], function (require) {
    "use strict";

    var core = require('web.core');
    var Widget = require('web.Widget');
    var rpc = require('web.rpc');
    var AbstractAction = require('web.AbstractAction');
    var field_utils = require('web.field_utils');
    var QWeb = core.qweb;
    var _t = core._t;

    var CampaignAnalysisDashboard = AbstractAction.extend({
        template: 'CampaignAnalysisDashboard',
        events: {
            'click .o_campaign_analysis_refresh': '_onRefresh',
            'change .date-filter-input': '_onDateFilterChange',
            'click .export-btn': '_onExportClick',
        },
        
        /**
         * @override
         */
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.action = action;
            this.context = action.context || {};
            this.campaignData = null;
            
            // Initialize dates from context or default to last 30 days
            var today = new Date();
            var thirtyDaysAgo = new Date();
            thirtyDaysAgo.setDate(today.getDate() - 30);
            
            this.dateFrom = this.context.date_from || field_utils.format.date(thirtyDaysAgo, {}, {format: 'YYYY-MM-DD'});
            this.dateTo = this.context.date_to || field_utils.format.date(today, {}, {format: 'YYYY-MM-DD'});
        },

        /**
         * @override
         */
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Set date inputs to current values
                self.$('.date-from-input').val(self.dateFrom);
                self.$('.date-to-input').val(self.dateTo);
                
                return self._fetchData();
            });
        },
        
        /**
         * Fetch the campaign analysis data
         * @private
         * @returns {Promise}
         */
        _fetchData: function () {
            var self = this;
            
            // Show loading state
            this.$('.o_campaign_analysis_content').empty().append(
                $('<div>').addClass('text-center p-5')
                    .append($('<i>').addClass('fa fa-spinner fa-spin fa-2x'))
                    .append($('<div>').addClass('mt-2').text(_t('Loading data...')))
            );
            
            // Convert dates to datetime format for the server
            var dateFrom = this.dateFrom ? this.dateFrom + ' 00:00:00' : false;
            var dateTo = this.dateTo ? this.dateTo + ' 23:59:59' : false;
            
            // First refresh the materialized view explicitly
            return rpc.query({
                model: 'crm.campaign.analysis.report',
                method: 'refresh_materialized_view',
                args: [],
                context: this.context,
            }).then(function() {
                // Then fetch the data
                return rpc.query({
                    model: 'crm.campaign.analysis.report',
                    method: 'get_campaign_stage_analysis',
                    args: [
                        dateFrom, 
                        dateTo
                    ],
                    context: self.context,
                });
            }).then(function (result) {
                self.campaignData = result;
                return self._renderContent();
            }).guardedCatch(function(error) {
                self.$('.o_campaign_analysis_content').empty().append(
                    $('<div>').addClass('alert alert-danger')
                        .text(_t('Error loading data: ') + error.message || _t('Unknown error'))
                );
                return Promise.reject(error);
            });
        },
        
        /**
         * Renders the dashboard content
         * @private
         * @returns {Promise}
         */
        _renderContent: function () {
            this.$('.o_campaign_analysis_content').empty();
            
            if (!this.campaignData || !this.campaignData.campaigns || !this.campaignData.stages || 
                Object.keys(this.campaignData.campaigns).length === 0) {
                this.$('.o_campaign_analysis_content').append($('<div>')
                    .addClass('alert alert-info')
                    .text(_t('No data available. Try adjusting your filters.')));
                return Promise.resolve();
            }
            
            var $content = $(QWeb.render('CampaignAnalysisTableTemplate', {
                campaigns: this.campaignData.campaigns,
                stages: this.campaignData.stages,
                dateFrom: this.dateFrom,
                dateTo: this.dateTo,
                formatPercentage: function(value) {
                    return value.toFixed(2) + '%';
                },
                getStageDisplay: function(stage) {
                    if (typeof stage === 'object' && stage !== null) {
                        return Object.values(stage)[0] || 'Unknown';
                    }
                    return stage;
                },
                shouldHighlight: function(stageName, percentage) {
                    stageName = String(stageName || '').toUpperCase();
                    if ((stageName.includes('JUNK') && percentage > 20) ||
                        ((stageName.includes('NOT CONNECTED') || stageName === 'NC') && percentage > 20) ||
                        ((stageName.includes('ADMISSION') || stageName === 'A') && percentage < 5) ||
                        ((stageName.includes('HOT PROSPECT') || stageName === 'HP' || 
                          stageName.includes('FUTURE PROSPECT') || stageName === 'FP') && percentage < 5)) {
                        return true;
                    }
                    return false;
                }
            }));
            
            this.$('.o_campaign_analysis_content').append($content);
            return Promise.resolve();
        },
        
        /**
         * Handle date filter change
         * @private
         */
        _onDateFilterChange: function (ev) {
            var $target = $(ev.currentTarget);
            if ($target.hasClass('date-from-input')) {
                this.dateFrom = $target.val();
            } else if ($target.hasClass('date-to-input')) {
                this.dateTo = $target.val();
            }
            this._fetchData();
        },
        
        /**
         * Handle refresh button click
         * @private
         */
        _onRefresh: function (ev) {
            ev.preventDefault();
            this._fetchData();
        },
        
        /**
         * Handle export button click
         * @private
         */
        _onExportClick: function (ev) {
            ev.preventDefault();
            var exportType = $(ev.currentTarget).data('type');
            
            // Create a context with the current date filters
            var ctx = _.extend({}, this.context, {
                date_from: this.dateFrom,
                date_to: this.dateTo,
                default_export_type: exportType,
            });
            
            // Open the export wizard
            this.do_action({
                name: _t('Export Campaign Analysis'),
                type: 'ir.actions.act_window',
                res_model: 'crm.campaign.analysis.export.wizard',
                views: [[false, 'form']],
                target: 'new',
                context: ctx,
            });
        }
    });

    // Add to the registry
    core.action_registry.add('campaign_analysis_dashboard', CampaignAnalysisDashboard);
    
    return CampaignAnalysisDashboard;

    return CampaignAnalysisDashboard;
});
