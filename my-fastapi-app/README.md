# My FastAPI App

This project is a FastAPI application that manages tasks and user authentication. It includes a background scheduler to check tasks and send notifications.

## Project Structure

```
my-fastapi-app
├── src
│   ├── main.py               # Entry point of the FastAPI application
│   ├── Auth
│   │   └── Auth.py           # Authentication-related functions
│   ├── Models
│   │   └── models.py         # Database models for Task and NotificationToken
│   ├── Routers
│   │   ├── user.py           # User management routes
│   │   └── task.py           # Task management routes
│   └── database.py           # Database connection and session management
├── requirements.txt           # Project dependencies
├── README.md                  # Project documentation
└── .env                       # Environment variables
```

## Setup Instructions

1. Clone the repository:
   ```
   git clone <repository-url>
   cd my-fastapi-app
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Set up your environment variables in the `.env` file.

5. Run the application using Uvicorn:
   ```
   uvicorn src.main:app --reload
   ```

## Usage

- Access the API documentation at `http://localhost:8000/docs`.
- Use the endpoints defined in the user and task routers for user management and task operations.

## Contributing

Feel free to submit issues or pull requests for improvements or bug fixes.