import random
import uuid
from datetime import timedelta, datetime
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from inventory.models import (
    Category, Supplier, Product, PurchaseOrder, PurchaseOrderItem, 
    StockTransaction, Customer, CustomerPayment, POSSale, ExpenseCategory, 
    Expense, HydraulicSow, PriceOverrideLog
)

class Command(BaseCommand):
    help = 'Overhauls database with comprehensive test data for Rich Land System.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('This will wipe all existing data. Proceeding...'))
        self.clear_data()

        # 1. Get or Create Admin User for logs
        admin_user = User.objects.filter(username='admin').first()
        if not admin_user:
            admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'password123')
            self.stdout.write("Created superuser: admin / password123")
        
        from django.contrib.auth.models import Group
        manager_group, _ = Group.objects.get_or_create(name='Manager')
        salesman_group, _ = Group.objects.get_or_create(name='Salesman')

        manager = User.objects.create_user('manager1', 'manager@example.com', 'password123')
        manager.groups.add(manager_group)
        
        salesman1 = User.objects.create_user('salesman1', 'salesman1@example.com', 'password123')
        salesman1.groups.add(salesman_group)
        
        salesman2 = User.objects.create_user('salesman2', 'salesman2@example.com', 'password123')
        salesman2.groups.add(salesman_group)
        
        all_users = [admin_user, manager, salesman1, salesman2]
        staff_users = [admin_user, manager]
        pos_users = [salesman1, salesman2, manager]

        self.stdout.write(f"Created users: manager1, salesman1, salesman2")

        # 2. Create Product Categories
        categories = [
            'Engine Parts', 'Suspension', 'Braking System', 'Electrical',
            'Fluids & Chemicals', 'Tires & Wheels', 'Accessories', 'Batteries',
            'Filters', 'Belts & Hoses'
        ]
        cat_objs = []
        for name in categories:
            cat, created = Category.objects.get_or_create(name=name)
            cat_objs.append(cat)
        self.stdout.write(f"Created {len(cat_objs)} categories.")

        # 3. Create Suppliers
        suppliers_data = [
            {'name': 'Global Auto Parts', 'contact': 'John Smith', 'email': 'john@globalauto.com', 'phone': '0917-123-4567'},
            {'name': 'Manila Rubber Corp', 'contact': 'Maria Cruz', 'email': 'maria@mrc.ph', 'phone': '0918-555-0101'},
            {'name': 'Lubricants Express', 'contact': 'David Lee', 'email': 'sales@lubex.com', 'phone': '02-8888-1234'},
            {'name': 'Davao Tires Inc.', 'contact': 'Roberto Go', 'email': 'rgo@davaotires.com', 'phone': '0922-111-2222'},
            {'name': 'Cebu Batteries', 'contact': 'Ana Lim', 'email': 'ana@cebubatt.com', 'phone': '032-231-4545'},
        ]

        sup_objs = []
        for data in suppliers_data:
            sup, created = Supplier.objects.get_or_create(name=data['name'], defaults={
                'contact_person': data['contact'],
                'email': data['email'],
                'phone': data['phone']
            })
            sup_objs.append(sup)
        self.stdout.write(f"Created {len(sup_objs)} suppliers.")
        
        # 4. Create Customers
        self.stdout.write("Creating customers...")
        
        # Ensure Walk-in Customer exists first
        walk_in_customer, _ = Customer.objects.get_or_create(
            name="Walk-in Customer", 
            defaults={'address': 'Store Counter'}
        )

        customers_data = [
            {'name': 'John Doe Garage', 'email': 'johndoe@example.com', 'phone': '0917-111-2222', 'address': '123 Main St, QC'},
            {'name': 'Maria\'s Auto Repair', 'email': 'maria@repair.com', 'phone': '0918-333-4444', 'address': '456 Service Rd, Pasig'},
            {'name': 'Speedy Transport', 'email': 'ops@speedy.ph', 'phone': '0919-555-6666', 'address': 'Cagayan de Oro City'},
            {'name': 'Lito Mechanic', 'email': 'lito@yahoo.com', 'phone': '0920-888-9999', 'address': 'Lapasan, CDO'},
        ]

        # Generate 20 additional random customers
        for i in range(1, 21):
            customers_data.append({
                'name': f'Auto Shop {i}',
                'email': f'customer{i}@example.com',
                'phone': f'09{random.randint(10, 99)}-{random.randint(100, 999)}-{random.randint(1000, 9999)}',
                'address': f'{random.randint(1, 999)} Street Name, City',
            })

        customer_objs = []
        for data in customers_data:
            cust, created = Customer.objects.get_or_create(name=data['name'], defaults=data)
            customer_objs.append(cust)
        self.stdout.write(f"Created {len(customer_objs)} customers.")
        
        # 5. Create Products (More comprehensive list)
        # Format: Name, SKU, Category, Price, Initial Stock Target
        raw_products = [
            ('Motolite Gold Battery 2SM', 'BAT-GOLD-2SM', 'Batteries', 6500.00, 50),
            ('Motolite Enduro Battery 1SM', 'BAT-END-1SM', 'Batteries', 4500.00, 40),
            ('Shell Helix Ultra 5W-40 (4L)', 'OIL-SH-5W40-4L', 'Fluids & Chemicals', 2800.00, 100),
            ('Shell Helix HX7 10W-40 (1L)', 'OIL-SH-HX7-1L', 'Fluids & Chemicals', 450.00, 200),
            ('Brembo Brake Pads (Vios Front)', 'BRK-PAD-VIOS-F', 'Braking System', 3500.00, 30),
            ('Bendix Brake Shoe (Rear)', 'BRK-SHOE-GEN', 'Braking System', 1800.00, 40),
            ('Michelin Pilot Sport 4 225/45/R18', 'TIRE-MICH-18', 'Tires & Wheels', 12500.00, 20),
            ('Bridgestone Potenza 195/55/R15', 'TIRE-BRIDGE-15', 'Tires & Wheels', 4500.00, 40),
            ('NGK Spark Plug (Iridium)', 'SPK-NGK-IR', 'Engine Parts', 450.00, 500),
            ('Denso Spark Plug (Standard)', 'SPK-DENSO-STD', 'Engine Parts', 120.00, 500),
            ('Bosch Oil Filter (Toyota)', 'FLT-OIL-TOY', 'Filters', 350.00, 150),
            ('Vic Oil Filter (Mitsubishi)', 'FLT-OIL-MIT', 'Filters', 450.00, 150),
            ('Air Filter (Vios/Yaris)', 'FLT-AIR-VIOS', 'Filters', 650.00, 80),
            ('Cabin Filter (Carbon)', 'FLT-CAB-CARB', 'Filters', 850.00, 60),
            ('Fan Belt 4PK1210', 'BLT-4PK1210', 'Belts & Hoses', 450.00, 50),
            ('Timing Belt Kit (Innova)', 'BLT-TIM-INN', 'Engine Parts', 4500.00, 15),
            ('KYB Shock Absorber (Front)', 'SUS-KYB-FR', 'Suspension', 2800.00, 40),
            ('KYB Shock Absorber (Rear)', 'SUS-KYB-RR', 'Suspension', 2200.00, 40),
            ('Stabilizer Link', 'SUS-STAB-LNK', 'Suspension', 850.00, 60),
            ('Headlight Bulb H4 (Osram)', 'EL-BULB-H4', 'Electrical', 350.00, 100),
            ('LED Headlight Kit H4', 'EL-LED-H4', 'Electrical', 2500.00, 20),
            ('Car Horn (Bosch Europa)', 'ACC-HORN-EUR', 'Accessories', 3500.00, 25),
            ('Wiper Blade 24" (Bosch)', 'ACC-WIP-24', 'Accessories', 650.00, 50),
            ('Wiper Blade 16" (Bosch)', 'ACC-WIP-16', 'Accessories', 450.00, 50),
            ('Coolant (Prestone 1L)', 'CHEM-COOL-1L', 'Fluids & Chemicals', 280.00, 120),
            ('Brake Fluid DOT4 (500ml)', 'CHEM-BRK-DOT4', 'Fluids & Chemicals', 350.00, 100),
            ('Degreaser Spray', 'CHEM-DEG', 'Fluids & Chemicals', 180.00, 80),
            ('Microfiber Cloth (3pcs)', 'ACC-CLOTH', 'Accessories', 150.00, 200),
            ('Steering Wheel Cover', 'ACC-STR-COV', 'Accessories', 500.00, 30),
            ('Floor Matting (Deep Dish)', 'ACC-MAT-DISH', 'Accessories', 3500.00, 10),
        ]

        prod_objs = []
        for name, sku, cat_name, price, target_qty in raw_products:
            cat = Category.objects.get(name=cat_name)
            prod, created = Product.objects.get_or_create(
                sku=sku,
                defaults={
                    'name': name,
                    'category': cat,
                    'price': Decimal(price),
                    'quantity': 0, # Start at 0, populate via POs
                    'reorder_level': 10,
                    'status': 'ACTIVE'
                }
            )
            prod_objs.append(prod)

        self.stdout.write(f"Created {len(prod_objs)} products.")

        # 6. Populate Stock via Purchase Orders (To create Audit Trail)
        self.stdout.write("Populating stock via Purchase Orders...")
        
        # Create a "Received" PO for every product to establish base stock
        # We split this into a few POs to look realistic
        for i in range(5):
            supplier = random.choice(sup_objs)
            po = PurchaseOrder.objects.create(
                supplier=supplier,
                status='RECEIVED',
                order_date=timezone.now() - timedelta(days=random.randint(60, 365))
            )
            
            # Add 5-10 random products to this PO
            po_products = random.sample(prod_objs, k=random.randint(5, 10))
            
            for prod in po_products:
                # Find the target qty from our raw list
                target_qty = next(item[4] for item in raw_products if item[1] == prod.sku)
                qty = int(target_qty * random.uniform(0.8, 1.2)) # Vary slightly
                cost_price = prod.price * Decimal('0.7') # 30% margin
                
                PurchaseOrderItem.objects.create(
                    purchase_order=po,
                    product=prod,
                    quantity=qty,
                    price=cost_price
                )
                
                # Create Stock Transaction
                StockTransaction.objects.create(
                    product=prod,
                    transaction_type='IN',
                    transaction_reason='PO',
                    quantity=qty,
                    user=random.choice(staff_users),
                    notes=f"Received from PO {po.order_id}",
                    timestamp=po.order_date
                )
                
                prod.quantity += qty
                prod.last_purchase_date = po.order_date
                prod.save()

        # Create some PENDING and COMPLETED POs
        for _ in range(5):
            PurchaseOrder.objects.create(
                supplier=random.choice(sup_objs),
                status=random.choice(['PENDING', 'COMPLETED']),
                order_date=timezone.now() - timedelta(days=random.randint(1, 10))
            )

        # 6.5. Generate Product Edit History (Audit Trail)
        self.stdout.write("Generating product edit history...")
        for prod in random.sample(prod_objs, k=10):
            # Simulate 2-4 edits per selected product
            for _ in range(random.randint(2, 4)):
                editor = random.choice(staff_users)
                # Randomly change price or reorder level
                if random.random() < 0.5:
                    prod.price = prod.price * Decimal(random.uniform(0.95, 1.05))
                else:
                    prod.reorder_level = random.randint(5, 20)
                
                # django-simple-history records changes on save
                # We can't easily backdate history records without more complex logic,
                # but we can at least show different users made changes.
                prod._history_user = editor 
                prod.save()

        # 7. Create Expenses
        self.stdout.write("Creating expense categories and expenses...")
        exp_cats_data = ['Rent', 'Utilities', 'Salaries', 'Supplies', 'Marketing']
        exp_cat_objs = []
        for name in exp_cats_data:
            cat, _ = ExpenseCategory.objects.get_or_create(name=name)
            exp_cat_objs.append(cat)
        
        # Generate expenses for last 12 months
        for _ in range(150): 
            random_days = random.randint(0, 365)
            exp_date = timezone.now().date() - timedelta(days=random_days)
            Expense.objects.create(
                category=random.choice(exp_cat_objs),
                description=f"Sample {random.choice(exp_cat_objs).name} expense",
                amount=Decimal(random.uniform(500, 15000)).quantize(Decimal('0.01')),
                expense_date=exp_date,
                recorded_by=random.choice(staff_users)
            )

        # 8. Create Hydraulic SOWs (Mixed: Quotes, Paid, Charged)
        self.stdout.write("Creating Hydraulic SOWs...")
        for i in range(20):
            random_days = random.randint(0, 90)
            sow_date = timezone.now() - timedelta(days=random_days)
            
            # Mix of Walk-in and Named
            is_walkin = random.random() < 0.3
            cust = walk_in_customer if is_walkin else random.choice(customer_objs)
            
            sow_user = random.choice(pos_users)
            sow = HydraulicSow.objects.create(
                customer=cust, created_by=sow_user, hose_type=f"Type {random.choice(['A', 'B', 'C'])}",
                diameter=f"1/{random.randint(2,8)}", application=f"Excavator Arm {i+1}",
                cost=Decimal(random.uniform(1500, 8000)).quantize(Decimal('0.01'))
            )
            sow.date_created = sow_date
            sow.save()

            # 70% chance it's a charged job (Receipt generated)
            if random.random() < 0.7:
                # If walk-in, it's CASH. If named, could be CREDIT or CASH.
                if is_walkin:
                    pm = 'CASH'
                    paid = sow.cost
                else:
                    pm = random.choice(['CREDIT', 'CASH'])
                    paid = 0 if pm == 'CREDIT' else sow.cost
                
                POSSale.objects.create(
                    receipt_id=sow.sow_id, 
                    customer=cust, 
                    cashier=sow_user, 
                    payment_method=pm, 
                    total_amount=sow.cost, 
                    amount_paid=paid,
                    notes=f"Hydraulic Job #{sow.id}", 
                    timestamp=sow_date
                )

        # 9. Generate POS History (The heavy lifting)
        self.stdout.write("Generating POS transaction history...")
        end_date = timezone.now()
        start_date = end_date - timedelta(days=180) # Last 6 months
        start_date = start_date.replace(day=1)
        current_dt = start_date

        while current_dt < end_date:
            if current_dt.month == 12:
                next_month = current_dt.replace(year=current_dt.year+1, month=1, day=1)
            else:
                next_month = current_dt.replace(month=current_dt.month+1, day=1)
            
            days_in_month = (next_month - current_dt).days
            # Target ~500k - 1M per month for realistic data
            target_revenue = Decimal(random.uniform(500000, 1000000))
            current_revenue = Decimal('0')
            
            self.stdout.write(f"  - Generating {current_dt.strftime('%B %Y')}: Target PHP {target_revenue:,.2f}")
            
            while current_revenue < target_revenue:
                day_offset = random.randint(0, days_in_month - 1)
                hour = random.randint(8, 18)
                minute = random.randint(0, 59)
                txn_date = current_dt + timedelta(days=day_offset, hours=hour, minutes=minute)
                if txn_date > end_date: txn_date = end_date

                is_walk_in = random.random() < 0.5
                customer = walk_in_customer if is_walk_in else random.choice(customer_objs)
                
                if is_walk_in:
                    payment_method = random.choice(['CASH', 'CASH', 'GCASH', 'BANK', 'CARD'])
                else:
                    payment_method = random.choice(['CASH', 'CREDIT', 'CREDIT', 'CARD', 'GCASH', 'BANK'])

                sale_user = random.choice(pos_users)
                sale_record = POSSale.objects.create(
                    receipt_id=f"REC-{uuid.uuid4().hex[:8].upper()}",
                    cashier=sale_user, customer=customer, payment_method=payment_method, timestamp=txn_date
                )
                
                total_cost = Decimal('0')
                num_items = random.randint(1, 5)
                selected_products = random.sample(prod_objs, k=num_items)
                
                for product in selected_products:
                    # Magic restock if low to prevent negative stock in simulation
                    if product.quantity < 10:
                        restock_qty = 50
                        st_restock = StockTransaction.objects.create(
                            product=product,
                            transaction_type='IN',
                            transaction_reason='CORRECTION',
                            quantity=restock_qty,
                            user=random.choice(staff_users),
                            notes="Automatic restock during seeding"
                        )
                        st_restock.timestamp = txn_date
                        st_restock.save(update_fields=['timestamp'])
                        product.quantity += restock_qty
                        product.save(update_fields=['quantity'])
                        
                    qty = random.randint(1, 4)
                    
                    # Simulate custom price override (5% chance)
                    selling_price = product.price
                    if random.random() < 0.05:
                        original_price = product.price
                        selling_price = original_price * Decimal('0.9') # 10% discount
                        sale_record.has_price_override = True
                        PriceOverrideLog.objects.create(
                            pos_sale=sale_record,
                            product=product,
                            salesman=sale_user,
                            original_price=original_price,
                            override_price=selling_price,
                            reason=random.choice(["Valued Customer", "Bulk Discount", "Store Promotion", "Damaged Packaging"]),
                            timestamp=txn_date
                        )

                    StockTransaction.objects.create(
                        product=product, pos_sale=sale_record, transaction_type='OUT',
                        transaction_reason='SALE', quantity=qty, selling_price=selling_price,
                        user=sale_user, notes=f"POS Sale: {sale_record.receipt_id}",
                        timestamp=txn_date
                    )
                    
                    product.quantity -= qty
                    product.save()
                    total_cost += (selling_price * qty)

                if total_cost > 0:
                    sale_record.total_amount = total_cost
                    if payment_method != 'CREDIT': sale_record.amount_paid = total_cost
                    sale_record.save()
                    current_revenue += total_cost
                else:
                    sale_record.delete()
            
            current_dt = next_month

        # 10. Generate Payments for Credit Sales
        self.stdout.write("Generating customer payments for credit sales...")
        credit_sales = POSSale.objects.filter(payment_method='CREDIT')
        for sale in credit_sales:
            # 60% chance they paid it
            if random.random() < 0.6:
                payment_date = sale.timestamp + timedelta(days=random.randint(1, 15))
                if payment_date > timezone.now(): payment_date = timezone.now()
                
                # Full or partial payment
                payment_amount = sale.total_amount if random.random() < 0.7 else sale.total_amount / 2
                
                CustomerPayment.objects.create(
                    customer=sale.customer, sale_paid=sale, amount=payment_amount.quantize(Decimal('0.01')),
                    payment_date=payment_date, recorded_by=random.choice(pos_users), notes="Seed data payment"
                )

        # 11. Generate Returns and Damages
        self.stdout.write("Generating returns and damages...")
        for _ in range(20):
            sale_to_return = POSSale.objects.filter(items__isnull=False).order_by('?').first()
            if sale_to_return:
                item_to_return = sale_to_return.items.order_by('?').first()
                if item_to_return:
                    return_date = sale_to_return.timestamp + timedelta(days=random.randint(1,3))
                    st = StockTransaction.objects.create(
                        product=item_to_return.product, transaction_type='IN', transaction_reason='RETURN',
                        quantity=1, selling_price=item_to_return.selling_price,
                        pos_sale=sale_to_return, # Link return to original sale
                        user=random.choice(pos_users),
                        notes=f"Return for {sale_to_return.receipt_id}"
                    )
                    st.timestamp = return_date
                    st.save()
                    item_to_return.product.quantity += 1
                    item_to_return.product.save()

        for _ in range(15):
            product = random.choice(prod_objs)
            if product.quantity > 0:
                with transaction.atomic():
                    product_to_damage = Product.objects.select_for_update().get(pk=product.pk)
                    if product_to_damage.quantity > 0:
                        product_to_damage.quantity -= 1
                        product_to_damage.save()
                        damage_date = timezone.now() - timedelta(days=random.randint(1,180))
                        st = StockTransaction.objects.create(
                            product=product_to_damage, transaction_type='OUT', transaction_reason='DAMAGE',
                            quantity=1, user=random.choice(staff_users),
                            notes=random.choice(["Damaged during handling (seed)", "Expired item", "Lost in transit"])
                        )
                        st.timestamp = damage_date
                        st.save()

        self.stdout.write(self.style.SUCCESS('Successfully seeded database with sample data!'))

    def clear_data(self):
        """Deletes data from models to prepare for fresh seeding."""
        self.stdout.write("Clearing old data...")
        # Order is important to respect foreign key constraints
        # Delete models with foreign keys first.
        models_to_clear = [
            PriceOverrideLog, StockTransaction, PurchaseOrderItem, CustomerPayment,
            POSSale, HydraulicSow, PurchaseOrder, Expense, Product,
            Customer, Supplier, Category, ExpenseCategory
        ]
        for model in models_to_clear:
            try:
                if model.objects.exists():
                    model.objects.all().delete()
                    self.stdout.write(f"  - Cleared {model.__name__}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error clearing {model.__name__}: {e}"))

        # Clear non-superuser users
        User.objects.filter(is_superuser=False).delete()
        self.stdout.write("  - Cleared non-superuser users")