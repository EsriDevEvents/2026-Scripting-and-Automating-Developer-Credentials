import "dotenv/config";
import { ArcGISIdentityManager, request } from "@esri/arcgis-rest-request";

/**
 * Get environment variables from the .env file. Loading this file is handled by the dotenv package.
 */
const { USERNAME, PASSWORD } = process.env as {
  USERNAME: string;
  PASSWORD: string;
};

/**
 * Create an authentication manager using the provided credentials.
 */
const authentication = await ArcGISIdentityManager.signIn({
  username: USERNAME,
  password: PASSWORD,
});

/**
 * Define a start time for our search as the start of the day today.
 */
const TODAY = new Date();
TODAY.setHours(0, 0, 0, 0);

/**
 * Define an end time for our search as the end of the day 30 days from now.
 */
const NEXT_30_DAYS = new Date();
NEXT_30_DAYS.setDate(NEXT_30_DAYS.getDate() + 30);
NEXT_30_DAYS.setHours(23, 59, 59, 999);

/**
 * Make a request to the API to get all tokens that will expire in the next 30 days.
 */
const tokens = await request(
  "https://www.arcgis.com/sharing/rest/portals/self/apiTokens",
  {
    authentication,
    params: {
      num: 100,
      startExpirationDate: TODAY,
      endExpirationDate: NEXT_30_DAYS,
    },
  }
);

/**
 * Will contain the itemId and client id op all tokens. Note that each API key
 * item can have up to 2 tokens so each item might appeas twice in the list.
 */
console.log(tokens);
