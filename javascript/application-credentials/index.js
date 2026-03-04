import express from 'express'
import { engine } from 'express-handlebars';
import { ApplicationCredentialsManager } from '@esri/arcgis-rest-request';
import dotenv from 'dotenv';
dotenv.config();

const app = express()

app.engine('handlebars', engine())
app.set('view engine', 'handlebars')

app.get('/', async (req, res) => {

  // create a session using application credentials
  const session = ApplicationCredentialsManager.fromCredentials({
    clientId: process.env.CLIENT_ID,
    clientSecret: process.env.CLIENT_SECRET
  })

  //ensure the session is valid and has a token
  try {
    await session.getToken();
  } catch (e) {
    console.error('Error generating token', e);
    return res.status(500).send('Error generating token');
  }
  const token = await session.getToken();

  res.render('index', { accessToken: token, layout: false })
});

app.get('/token', async (req, res) => {
  const session = ApplicationCredentialsManager.fromCredentials({
    clientId: process.env.CLIENT_ID,
    clientSecret: process.env.CLIENT_SECRET
  });

  try {
    const token = await session.getToken();
    res.json({ accessToken: token });
  } catch (e) {
    console.error('Error generating token', e);
    res.status(500).json({ error: 'Error generating token' });
  }
});

app.listen(3000, () => {
  console.log('Server is running on http://localhost:3000')
})