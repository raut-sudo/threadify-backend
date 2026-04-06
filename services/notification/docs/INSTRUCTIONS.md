I want to now create a notifications service .

very simple service , 

the main function to store the notifications emitted form the thread service 
- 1. notification type : commented on user's post
- 2. notification type : user mentione using @ (in post/comment)

- then we need to store these notificaiton and when the /notifications is hit gett all the notifications (in descending order of their creation ofc )
- notifications will have statuses , "read" and "unread"

- also if the user is online then they msut be notified like the whatsapp using websockets realtime, 1 unread , 2 unread (will be implemented later)

- Let's plan out !!
