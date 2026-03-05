import express from 'express'
import { engine } from 'express-handlebars';
import { ApplicationCredentialsManager } from '@esri/arcgis-rest-request';
import dotenv from 'dotenv';

// Load environment variables from .env file
dotenv.config();

// Create an Express application and set up Handlebars as the view engine
const app = express()
app.engine('handlebars', engine())
app.set('view engine', 'handlebars')

// Function to get a fresh client token using the ApplicationCredentialsManager
async function getFreshClientToken() {
  const session = ApplicationCredentialsManager.fromCredentials({
    clientId: process.env.CLIENT_ID,
    clientSecret: process.env.CLIENT_SECRET,
    duration: 2
  });

  return {
    accessToken: await session.getToken(),
    tokenExpiration: session.expires
  };
}

// Define the root route to render the index page with the token information
// In a production app you might want to protect this route with a user login or some other mechanism
app.get('/', async (req, res) => {
  // Get a fresh token to pass to the client for initial page load
  try {
    const token = await getFreshClientToken();
  } catch (e) {
    console.error('Error generating token', e);
    return res.status(500).send('Error generating token');
  }

  // Render the index page and pass the token information to the client for use in the JavaScript code
  res.render('index', { ...token, layout: false });
});

// Define a route to generate a new token when the client requests it (e.g. when refreshing the token)
app.post('/token', async (req, res) => {
  try {
    const token = await getFreshClientToken();
    res.json(token);
  } catch (e) {
    console.error('Error generating token', e);
    res.status(500).json({ error: 'Error generating token' });
  }
});

app.listen(3000, () => {
  console.log('Server is running on http://localhost:3000')
})