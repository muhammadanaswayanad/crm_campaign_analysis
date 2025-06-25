odoo.define('crm_campaign_analysis.campaign_analysis_dashboard', ['web.core', 'web.Widget', 'web.rpc', 'web.AbstractAction'], function (require) {
    "use strict";

    var core = require('web.core');
    var Widget = require('web.Widget');
    var rpc = require('web.rpc');
    var AbstractAction = require('web.AbstractAction');
    var QWeb = core.qweb;
    var _t = core._t;

    var CampaignAnalysisDashboard = AbstractAction.extend({
        template: 'CampaignAnalysisDashboard',
        events: {
            'click .o_campaign_analysis_refresh': '_onRefresh',
        },
        
        /**
         * @override
         */
        init: function (parent, action) {
            this._super.apply(this, arguments);
            this.action = action;
            this.context = action.context || {};
            this.campaignData = null;
        },

        /**
         * @override
         */
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
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
            return rpc.query({
                model: 'crm.campaign.analysis.report',
                method: 'get_campaign_stage_analysis',
                args: [
                    this.context.date_from || false, 
                    this.context.date_to || false
                ],
                context: this.context,
            }).then(function (result) {
                self.campaignData = result;
                return self._renderContent();
            });
        },
        
        /**
         * Renders the dashboard content
         * @private
         * @returns {Promise}
         */
        _renderContent: function () {
            this.$('.o_campaign_analysis_content').empty();
            
            if (!this.campaignData || !this.campaignData.campaigns || !this.campaignData.stages) {
                this.$('.o_campaign_analysis_content').append($('<div>')
                    .addClass('alert alert-info')
                    .text(_t('No data available. Try adjusting your filters.')));
                return Promise.resolve();
            }
            
            var $content = $(QWeb.render('CampaignAnalysisTableTemplate', {
                campaigns: this.campaignData.campaigns,
                stages: this.campaignData.stages,
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
         * Formats a percentage value
         * @private
         * @param {float} value
         * @returns {string}
         */
        _formatPercentage: function (value) {
            return value.toFixed(2) + '%';
        },
        
        /**
         * Gets the display name for a stage
         * @private
         * @param {mixed} stage
         * @returns {string}
         */
        _getStageDisplay: function (stage) {
            if (typeof stage === 'object' && stage !== null) {
                return Object.values(stage)[0] || 'Unknown';
            }
            return stage;
        },
        
        /**
         * Determines if a cell should be highlighted
         * @private
         * @param {string} stageName
         * @param {float} percentage
         * @returns {boolean}
         */
        _shouldHighlight: function (stageName, percentage) {
            stageName = String(stageName).toUpperCase();
            if ((stageName.includes('JUNK') && percentage > 20) ||
                ((stageName.includes('NOT CONNECTED') || stageName === 'NC') && percentage > 20) ||
                ((stageName.includes('ADMISSION') || stageName === 'A') && percentage < 5) ||
                ((stageName.includes('HOT PROSPECT') || stageName === 'HP' || 
                  stageName.includes('FUTURE PROSPECT') || stageName === 'FP') && percentage < 5)) {
                return true;
            }
            return false;
        },
        
        /**
         * Handle refresh button click
         * @private
         */
        _onRefresh: function () {
            this._fetchData();
        },
    });

    // Add to the registry - Adding console logs for debugging
    console.log('Registering campaign_analysis_dashboard client action');
    console.log('Registry before:', core.action_registry.map);
    core.action_registry.add('campaign_analysis_dashboard', CampaignAnalysisDashboard);
    console.log('Registry after:', core.action_registry.map);
    
    // Also add it with a different key just in case
    core.action_registry.add('crm_campaign_analysis.campaign_analysis_dashboard', CampaignAnalysisDashboard);

    return CampaignAnalysisDashboard;
});
