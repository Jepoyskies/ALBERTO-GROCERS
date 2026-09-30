/*
 * Purchase Order Admin Automation
 * Specifically designed for Django Admin with Select2 and jQuery
 */
(function() {
    'use strict';
    
    // Django provides jQuery as django.jQuery
    var $ = window.django ? window.django.jQuery : (window.jQuery || null);
    
    if (!$) {
        console.error("Purchase Order Admin Automation: jQuery not found.");
        return;
    }

    $(document).ready(function() {
        console.log("Purchase Order Admin Automation Active");

        /**
         * Core function to fetch and set price
         */
        function setPriceForSelect($select) {
            var productId = $select.val();
            var name = $select.attr('name');
            
            if (!productId || !name || !name.includes('product')) return;

            // Resolve the price field name based on the current row index
            // e.g., items-0-product -> items-0-price
            var priceFieldName = name.replace('-product', '-price');
            var $priceField = $('input[name="' + priceFieldName + '"]');

            if ($priceField.length) {
                // We use a relative URL to ensure compatibility across environments
                var url = '/inventory/products/' + productId + '/price/';
                
                $.ajax({
                    url: url,
                    dataType: 'json',
                    success: function(data) {
                        if (data.price) {
                            $priceField.val(data.price);
                            console.log("Auto-filled price for " + priceFieldName + ": " + data.price);
                            
                            // Visual feedback: Flash the field
                            $priceField.css('background-color', '#fff3cd');
                            setTimeout(function() {
                                $priceField.css('background-color', '');
                            }, 500);
                        }
                    },
                    error: function() {
                        console.error("Could not fetch price for product ID: " + productId);
                    }
                });
            }
        }

        /**
         * Event Listeners
         */
        
        // 1. Listen for Select2 selection (used by autocomplete_fields)
        $(document).on('select2:select', 'select', function(e) {
            setPriceForSelect($(this));
        });

        // 2. Listen for standard select change (fallback)
        $(document).on('change', '.field-product select', function() {
            setPriceForSelect($(this));
        });
    });
})();