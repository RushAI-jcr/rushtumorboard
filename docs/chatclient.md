# Chat Client — React UI

If you want to use the React client application instead of Teams, follow these steps:

1. Navigate to the democlient directory:
```bash
cd democlient
```

2. Install the dependencies:
```bash
npm install
```

3. Run the client application:
```bash
npm run dev
```

4. Open your browser to http://localhost:3000 to interact with the application.

5. You will need to login using the Microsoft authentication flow. Once logged in, you can create a new chat and start interacting with the GYN tumor board agents.

> Note: The client application uses Vite + FluentUI + Redux. It requires the FastAPI backend to be running. Make sure you have deployed the infrastructure or are running the server locally.