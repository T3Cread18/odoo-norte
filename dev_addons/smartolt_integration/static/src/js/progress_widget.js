odoo.define('smartolt_integration.progress_widget', function (require) {
    'use strict';

    var FormController = require('web.FormController');
    var FormView = require('web.FormView');
    var viewRegistry = require('web.view_registry');

    // Extender FormController para auto-refresh
    var ProgressFormController = FormController.extend({
        init: function () {
            this._super.apply(this, arguments);
            this._refreshInterval = null;
        },

        willStart: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                // Iniciar auto-refresh solo para el wizard de progreso
                if (self.modelName === 'smartolt.bulk.progress.wizard') {
                    self._startAutoRefresh();
                }
            });
        },

        _startAutoRefresh: function () {
            var self = this;
            console.log('Iniciando auto-refresh para wizard de progreso');
            
            this._refreshInterval = setInterval(function () {
                self._performAutoRefresh();
            }, 3000); // Cada 3 segundos
        },

        _performAutoRefresh: function () {
            var self = this;
            
            if (!this.model || !this.handle) {
                return;
            }

            var record = this.model.get(this.handle);
            if (record && record.data && record.data.state === 'running') {
                console.log('Auto-refreshing progress wizard...');
                
                this.model.reload(this.handle, {
                    keepChanges: true
                }).then(function () {
                    return self.renderer.confirmChange(self.handle, self.handle);
                }).catch(function (error) {
                    console.warn('Error en auto-refresh:', error);
                });
            } else if (record && record.data && record.data.state !== 'running') {
                // Detener auto-refresh si el proceso terminó
                self._stopAutoRefresh();
            }
        },

        _stopAutoRefresh: function () {
            if (this._refreshInterval) {
                console.log('Deteniendo auto-refresh');
                clearInterval(this._refreshInterval);
                this._refreshInterval = null;
            }
        },

        destroy: function () {
            this._stopAutoRefresh();
            this._super.apply(this, arguments);
        }
    });

    // Vista personalizada
    var ProgressFormView = FormView.extend({
        config: _.extend({}, FormView.prototype.config, {
            Controller: ProgressFormController,
        }),
    });

    // Registrar la vista
    viewRegistry.add('progress_form', ProgressFormView);

    return ProgressFormView;
});