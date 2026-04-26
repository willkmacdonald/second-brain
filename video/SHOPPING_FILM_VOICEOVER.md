# Second Brain Shopping Film Voiceover

Composition: `SecondBrainShoppingFilm`
Audio file: `public/fortive-demo-intro.mp3`
Measured duration: 142.84 seconds at 30 fps

## Script

**0:00-0:09**  
One voice capture becomes a coordinated shopping plan, an online order, and a complete evidence trail.

**0:09-0:30**  
The user speaks naturally: I want to buy onions, garlic, cilantro, steak, milk, Tylenol, and cat food. The phone keeps the experience simple: tap to record, listen, classify, then file the result.

**0:29-0:44**  
The capture appears in the Admin inbox as a shopping list, then moves into tasks by destination. Jewel-Osco gets the produce and milk, CVS gets Tylenol, Agora gets steak, and Chewy gets cat food as an automatic online order.

**0:44-1:05**  
The same request is traceable through the technical flow. In Microsoft Foundry, the request moves from mobile capture into AI Foundry, then to the classifier agent, the admin agent, Cosmos DB, and finally the Chewy connector. Each step keeps the same trace context, so the transaction can be followed end to end.

**1:05-1:20**  
The classifier agent runs with Foundry-managed instructions. The instructions define the buckets, check when a capture belongs in Admin, and require the file_capture tool so the decision is written with trace context.

**1:20-1:39**  
Then the admin agent applies its own instructions. It splits the shopping list by destination, routes grocery and pharmacy items as local errands, places the cat food order through Chewy, and writes the order evidence back with the same trace ID.

**1:39-2:00**  
For observability, the phone stays simple while the web shows the evidence. App Insights shows request volume, response time, failed requests, and availability; the trace panel follows one transaction across mobile capture, classifier, admin agent, Cosmos DB, and the Chewy connector.

**2:00-2:12**  
Evals start from the phone too. In Investigate, the user asks for a classifier eval, lets it run in the background, checks back for results, and sees the scored run without reading backend logs.

**2:12-2:23**  
Capture becomes action. Action becomes evidence. Evidence improves the system.
