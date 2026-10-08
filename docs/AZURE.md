# Connecting this proof of concept to Azure

This describes how the screening service would run in Azure, and what would change from the "local" POC. The score rules, the three list parsers, and the shape of a decision stay as they are. The choice of LLM model is out of scope here.

The supplier list would most likely lie in the company's own Azure subscription, in an EU region. Azure is the place the list is stored and screened. It is not uploaded as a file to the model provider.

A model call, when one happens, still sends one supplier and at most five candidates, the same as the current implementation.

## The supplier list

This is the largest change. The proof of concept has no supplier registry. A person types one name, or uploads a CSV, and the only stored business data is the screening history.

In Azure the supplier list is a table in the same database as the sanctions index.

One row is one supplier: the supplier id, legal name, country, optional registration number, and whether the supplier is active.

After an initial upload of data into Azure, we would have an "master" script, keeping the table current.

## What runs

One Container Apps environment, in a virtual network.

- The API and the UI are two containers. The UI calls the API on the internal address.
- A quarterly job reads the supplier table, takes the active snapshot id once, and screens every active supplier. A failed row is stored. The job continues with the next supplier.

The images live in a container registry in the same subscription. The quarterly job uses the API image.

## Database

Azure Database for PostgreSQL, same region, private endpoint. The sanctions tables move there. The supplier table is the new one. Schema changes are migrations, applied before a new revision serves traffic.

## Sanction files

The stored snapshot is copied once into a private blob container, one folder for that snapshot. Container disk is dropped on restart, so the files cannot stay there.

Which snapshot is active is a flag on the snapshot row in Postgres. The API and the quarterly job read that flag.

## Access

Analysts sign in with Entra ID. The API rejects calls without that login. The API, the UI, and the quarterly job use a managed identity for Postgres, blob storage, and Key Vault. The model API key is a Key Vault secret on the API and the quarterly job.

Postgres, blob storage, and Key Vault are on private endpoints. 

Outbound traffic is the list publishers and the model API.