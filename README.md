🌟 Key Features

- Advanced Registration System

  - Country code selection
  - CAPTCHA protection with configurable attempt limits
  - Email verification with queue system (cron job every 5 seconds)

- Product Management

  - Dynamic product catalog with pagination
  - Advanced sorting and filtering capabilities
  - File system-synchronized image management

- Shopping Experience

  - Smart cart system with quantity validation
  - Support for promotional campaigns
  - User-specific voucher system
  - Multiple payment methods (PayPal, Bobi)

- Comprehensive Dashboard

  - Six-month order analytics
  - Two-day detailed metrics
  - Customizable reporting system

- Advanced Reporting

  - JSON-based report configuration
  - Audit logging (events and errors)
  - Batch export to CSV and Excel
  - Sales analytics with multiple grouping options

- Product Management

  - CRUD operations with image synchronization
  - Bulk upload via CSV
  - Automated failed image cleanup
  - Status tracking system

- Order Management

  - Status workflow management
  - Database trigger protection
  - Comprehensive order history

- User Management

  - Role-based access control
  - Permission-based interface visibility
  - Staff management system


- Marketing Tools

  - Customizable email templates
  - Promotional campaign management
  - Target group creation and management
  - Voucher system with one-time use validation

🛠️ Technical Features

- Backend Systems

- Email System

  - Queue-based processing
  - Customizable templates
  - Automated sending via cron jobs


- Image Management

  - Filesystem synchronization
  - Status tracking
  - Automated cleanup for failed uploads


- Data Export

  - Asynchronous generation
  - Support for CSV and Excel formats
  - Batch processing for large datasets

💻 Security Features

- Access Control

  - Role-based permissions
  - Interface-level access management
  - Staff activity auditing

- Transaction Management

  - Status validation
  - Database triggers for data integrity
  - Order status protection


- Site
  
- Registration form with country codes drop down menu. Captcha which has fixed attempts and timeout if the use exceed's the limit (attempts and timeout can be adjusted).

![image](https://github.com/user-attachments/assets/52e7acc7-cc59-43d2-8aa4-6661f392aaa7)

- After successful registration verification link will be send to the email (with email queue, script that is executed by cron job every 5 seconds).

![image](https://github.com/user-attachments/assets/cddfba99-e97a-47c4-8b3e-025c2a53ee4a)

- The template of the email can be ajusted in the back office Mail Templates.

![image](https://github.com/user-attachments/assets/81f2adea-922b-48a5-841a-d3caad3611d2)

- Login page.

![image](https://github.com/user-attachments/assets/8e4e65c4-f972-4036-a68f-6dc7df04d3aa)

- Home page with pagination, sorting, and filtering (images are synced with the filesystem).

![image](https://github.com/user-attachments/assets/3a5b804a-ebe5-4f82-87a3-d4d473ade8e0)
![image](https://github.com/user-attachments/assets/27656aa9-cf27-4096-a150-c18b842fe08a)

- Cart: the store can have a promotion running and also vouchers for determined users (campaigns).
If we try to buy items and in the database we don't have enough quantity, the user will get a good understanding message.

![image](https://github.com/user-attachments/assets/cd16be63-1263-4bdc-9779-649f82e9e39c)

- Payment: when the user makes an order he goes in the payment interface (order has status is 'Ready for paying').
If the order status is not 'Ready for paying' when he tries to pay, he will get understanding message.
When the user wants to pay with Bobi method, he must enter the exact value in the final price

![image](https://github.com/user-attachments/assets/8dacd405-fa63-4188-b991-0d27f143b097)

- When user is using PayPal

![image](https://github.com/user-attachments/assets/ba6d15d6-a232-43e2-b117-cdb2ff8f5a76)
![image](https://github.com/user-attachments/assets/4ec33e40-e68c-44e1-a6e0-0402c17eabf7)

- Back office

- Dashboard that gives information for orders(for last six months and last two days).

![image](https://github.com/user-attachments/assets/c8c71c87-d379-47a7-a446-c33480b03ac6)

- Every report is described with json object. Front end is made from this json and back end is following the same pattern.
In the back end we just need to write the query. So for new report we need json object sql.
- Report for audits (can be filtered by subsystem and log type (event or error)). Even is when someone registers in the site,
make a purchase, change roles e.t.c. Error is when user makes a mistake - type wrong passord, types wrong url, tries to make something stupid.
All reports can be downloaded in csv and excel (download is on baches. I am using async generator in js and generator in python).

![image](https://github.com/user-attachments/assets/7010468c-852a-4d3f-9117-ae16b45a0583)
![image](https://github.com/user-attachments/assets/a6439ec3-8866-491e-9d78-9c9832622655)

- CRUD Products: images are synced with file system. In the database i am storing the path to the filesystem, not the
picture in binary. When new product is made the pictures have different statuses and if sonething goes wrong the status is Failed.
And on every hour script is runned to check for failed images and delete them. Products can be uploaded from csv file

![image](https://github.com/user-attachments/assets/01788ba9-a045-4742-a317-a03237d3cea5)

- Create Product
![image](https://github.com/user-attachments/assets/2286c80e-188c-47b3-bb0c-63cb9efeddbd)

- Edit Product

![image](https://github.com/user-attachments/assets/14bcf28e-ec8e-4391-abd8-c1496049c909)

- Report sales: Detailed report for every sale. Can be grouped by day, month, year and see the totals under
the result columns. Can be exported in csv and excel.

![image](https://github.com/user-attachments/assets/f8479ff9-c201-43b8-a1dd-5643c1f7c4f5)
![image](https://github.com/user-attachments/assets/130db937-a596-433d-b719-d7b25f729980)

- CRUD Orders: here we can create new order, or edit one. The status on the order can't be made from 'Paid' to 'Ready for paying',
it can be changed only from 'Ready for paying' to 'Paid'. I am using db trigger 

![image](https://github.com/user-attachments/assets/7afd983a-f5ef-458a-a4e6-72b978c2cf69)
![image](https://github.com/user-attachments/assets/6716c899-a8b5-4d2c-ae7f-a59c2a446803)

- Create Order

![image](https://github.com/user-attachments/assets/89ac6e4f-3b10-4822-a14d-b1b7e5055f90)

- Edit Order

![image](https://github.com/user-attachments/assets/455bdc2b-2403-47fe-98a2-6b179f5427c4)

- CRUD Users

![image](https://github.com/user-attachments/assets/686d61b7-ee29-4dc5-902b-a239df33417b)

- Create User

![image](https://github.com/user-attachments/assets/70301d05-c348-4295-9e3e-71e523a59fb5)

- Edit User

![image](https://github.com/user-attachments/assets/9b2a9822-9539-4a1c-b3fb-28d42592e884)

- CRUD Staff: back office users are the staff they have roles and permissions based on the role

![image](https://github.com/user-attachments/assets/a59f4546-2e12-480c-bed0-96dd5a8ba9ae)
![image](https://github.com/user-attachments/assets/227c6740-918f-43a6-b07f-1ce87daadded)

- CRUD Roles: every role has permissions for different interfaces. If a user has permission to
read a interface, but don't have permission to edit or create, the buttons won't be visible.

![image](https://github.com/user-attachments/assets/e4df3a79-1dbc-4bf2-b4a6-2795adf2ef22)

- Edit Role

![image](https://github.com/user-attachments/assets/b6949bc9-0ddb-40af-9186-677dbb93d905)
![image](https://github.com/user-attachments/assets/34e07fa6-e4ac-461a-9b61-15ac99b04726)

- Mail Templates

- Template for Verification Email
![image](https://github.com/user-attachments/assets/05afd368-deb3-40ce-a437-c5d98628ffe6)

- Template for Purchase Email

![image](https://github.com/user-attachments/assets/010080e3-360d-40fb-9a26-c50954110df3)

- Template for Payment Email

![image](https://github.com/user-attachments/assets/a84af2dd-37a6-4b62-b1ee-899a5f9b1395)

- Report Users Orders: here can be seen how much money every user had made in the last day, last week, and last year

![image](https://github.com/user-attachments/assets/cc30212d-67ef-4285-9015-e4b214e00b18)
![image](https://github.com/user-attachments/assets/6daec6f7-5109-4a32-ae4b-43953d41707a)

- CRUD Promotions: promotions are for every user in the shop here we can manage them. I have a script that runs every minute to check for the promotions
status. If the promitions has ended to change the status.

![image](https://github.com/user-attachments/assets/f79e77e2-c2ec-4ab3-8371-7103fdea74ca)

- Create Promotion

![image](https://github.com/user-attachments/assets/a6152aab-0227-40da-ab1d-71ff45d0a25b)

- Edit Promotion

![image](https://github.com/user-attachments/assets/1f5b85f8-c530-4f5e-8e43-c80e005488fe)

- CRUD Target Groups: target groups are a group of people that have common thing. For example we want to target all users in our store,
which have name Ivan, so we can give them a discount voucher. When we enter the data in the fields and click filter we are filtering the
registered users in our store. When they are filtered we can make the target group with the create button. If we want to see all the available target
groups we have to click on show target groups. Target groups can be exported to csv.

- Showed target groups
![image](https://github.com/user-attachments/assets/32256f17-db11-4093-b662-464874c49c97)

- Filtered user by birth date

![image](https://github.com/user-attachments/assets/0d7d0db4-fe72-4871-8503-8b6c64a61d32)

- Create Traget Group when users are filtered

![image](https://github.com/user-attachments/assets/abab0673-2e28-4bcc-9598-11455ae813ae)

- CRUD Vouchers: every user can have a voucher. If a voucher is used by the user, he can't use it again
vouchers are one time price discount, while the promotions are on a time periods

![image](https://github.com/user-attachments/assets/7f63c823-0e0b-4b3f-81ad-8a827f394461)

- Create Voucher

![image](https://github.com/user-attachments/assets/9f50d3c6-8b9e-4afe-a78a-e9c806117c30)

- Edit Voucher

![image](https://github.com/user-attachments/assets/759dc4b2-5b8c-4b66-a13b-a0179e28f2d5)

- Send Mails
  
- Mail for made order
  
![image](https://github.com/user-attachments/assets/9cc475f0-676a-4e1a-b378-a2eb2fd1ad9c)

- Mail for payed order

![image](https://github.com/user-attachments/assets/4ce0334f-558b-4cc3-a2e9-3eb5297984a2)







































  





