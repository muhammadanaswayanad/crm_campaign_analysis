odoo.define('crm_campaign_analysis.campaign_analysis_custom_view', [
    'web.AbstractView',
    'web.AbstractController',
    'web.AbstractRenderer',
    'web.AbstractModel',
    'web.core',
    'web.view_registry',
    'web._'
], function (require) {
    "use strict";

    var AbstractView = require('web.AbstractView');
    var AbstractController = require('web.AbstractController');
    var AbstractRenderer = require('web.AbstractRenderer');
    var AbstractModel = require('web.AbstractModel');
    var core = require('web.core');
    var view_registry = require('web.view_registry');
    var _ = require('web._');

    var QWeb = core.qweb;
    var _lt = core._lt;

    var CustomModel = AbstractModel.extend({
        /**
         * @override
         */
        init: function () {
            this._super.apply(this, arguments);
            this.data = null;
        },

        /**
         * @override
         */
        get: function () {
            return {
                campaignData: this.data,
            };
        },

        /**
         * @override
         */
        load: function (params) {
            this.modelName = params.modelName;
            this.domain = params.domain;
            this.context = params.context;
            return this._fetchData();
        },

        /**
         * @override
         */
        reload: function (handle, params) {
            if (params && params.domain) {
                this.domain = params.domain;
            }
            if (params && params.context) {
                this.context = params.context;
            }
            return this._fetchData();
        },

        /**
         * Fetch the campaign analysis data
         * @private
         * @returns {Promise}
         */
        _fetchData: function () {
            var self = this;
            return this._rpc({
                model: 'crm.campaign.analysis.report',
                method: 'get_campaign_stage_analysis',
                args: [
                    this.context.date_from || false, 
                    this.context.date_to || false
                ],
                context: this.context,
            }).then(function (result) {
                self.data = result;
                return result;
            });
        },
    });

    var CustomRenderer = AbstractRenderer.extend({
        template: 'CampaignAnalysisCustomView',
        
        /**
         * @override
         */
        init: function (parent, state, params) {
            this._super.apply(this, arguments);
            this.campaignData = state.campaignData;
        },

        /**
         * @override
         */
        updateState: function (state) {
            this._super.apply(this, arguments);
            this.campaignData = state.campaignData;
            return this._render();
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
         * @override
         */
        _render: function () {
            var self = this;
            this.$el.empty();
            
            if (!this.campaignData || !this.campaignData.campaigns || !this.campaignData.stages) {
                this.$el.append($('<div>').addClass('o_view_nocontent').text('No data available. Try adjusting your filters.'));
                return Promise.resolve();
            }

            // Render the table with the campaign data
            var $table = $(QWeb.render('CampaignAnalysisTableTemplate', {
                campaigns: this.campaignData.campaigns,
                stages: this.campaignData.stages,
                formatPercentage: this._formatPercentage,
                getStageDisplay: function(stage) {
                    if (typeof stage === 'object' && stage !== null) {
                        // If it's a translation dict, get the first value
                        return Object.values(stage)[0] || 'Unknown';
                    }
                    return stage;
                },
                shouldHighlight: function(stageName, percentage) {
                    var name = String(stageName || '').toUpperCase();
                    if ((name.includes('JUNK') && percentage > 20) ||
                        ((name.includes('NOT CONNECTED') || name === 'NC') && percentage > 20) ||
                        ((name.includes('ADMISSION') || name === 'A') && percentage < 5) ||
                        ((name.includes('HOT PROSPECT') || name === 'HP' || 
                          name.includes('FUTURE PROSPECT') || name === 'FP') && percentage < 5)) {
                        return true;
                    }
                    return false;
                }
            }));

            this.$el.append($table);
            return Promise.resolve();
        },
    });

    var CustomController = AbstractController.extend({
        /**
         * @override
         */
        renderButtons: function ($node) {
            if ($node) {
                this.$buttons = $(QWeb.render('CampaignAnalysisCustomViewButtons', {}));
                this.$buttons.find('.o_campaign_analysis_refresh').on('click', this._onRefresh.bind(this));
                this.$buttons.appendTo($node);
            }
        },

        /**
         * Handle refresh button click
         * @private
         */
        _onRefresh: function () {
            this.update({}, {reload: true});
        },
    });

    var CustomView = AbstractView.extend({
        display_name: _lt('Campaign Analysis'),
        icon: 'fa-pie-chart',
        config: _.extend({}, AbstractView.prototype.config, {
            Model: CustomModel,
            Controller: CustomController,
            Renderer: CustomRenderer,
        }),
        viewType: 'campaign_analysis',
        
        /**
         * @override
         */
        init: function (viewInfo, params) {
            this._super.apply(this, arguments);
            this.loadParams.type = 'campaign_analysis';
        },
    });

    view_registry.add('campaign_analysis', CustomView);
    
    return {
        CustomModel: CustomModel,
        CustomRenderer: CustomRenderer,
        CustomController: CustomController,
        CustomView: CustomView,
    };
});
