import "dotenv/config";
import { ArcGISIdentityManager } from "@esri/arcgis-rest-request";
import { searchItems, SearchQueryBuilder } from "@esri/arcgis-rest-portal";
import { getOAuthApp } from "@esri/arcgis-rest-developer-credentials";

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
 * Get all registered OAuth apps in the organization. This uses the searchItems function and the `nextPage()`
 * method to get all items in the organization that are registered applications. This will include both oAuth
 * apps and API keys.
 */
async function getAllRegisteredApps() {
  const user = await authentication.getUser();
  const orgId = user.orgId as string;

  // `SearchQueryBuilder` is a helper class that makes it easier to build complex queries.
  const query = new SearchQueryBuilder()
    .match("Application")
    .in("type")
    .and()
    .match("Application")
    .in("typekeywords")
    .and()
    .match("Registered App")
    .in("typekeywords")
    .and()
    .match(orgId)
    .in("orgid");

  let lastResponse = await searchItems({
    q: query,
    num: 1, // deliberatly set to 1 to simulate pagination
    authentication,
  });

  let allItems = lastResponse.results;

  // Keep getting the next page until there are no more pages.
  while (lastResponse.nextPage) {
    lastResponse = await lastResponse.nextPage();
    allItems = allItems.concat(lastResponse.results);
  }

  return allItems;
}

/**
 * Now we cae call our function and get all registered apps
 */
const registeredApps = await getAllRegisteredApps();

/**
 * Get the details of each registered app
 */
const appDetails = await Promise.all(
  registeredApps.map((app) => {
    return getOAuthApp({
      itemId: app.id,
      authentication,
    });
  })
);

/**
 * Output the details of each app
 */
appDetails.forEach((app) => {
  console.table({
    title: app.item.title,
    itemId: app.item.id,
    redirectUris: app.redirect_uris.join(", "),
    link: `https://www.arcgis.com/home/item.html?id=${app.item.id}`,
  });
});
