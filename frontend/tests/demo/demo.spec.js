import {test,expect} from "@playwright/test";

for (const width of [390,1440]) {
  test(`populated demo, cited assistant and decisions at ${width}px`,async({page})=>{
    const errors=[];page.on("pageerror",e=>errors.push(e.message));
    await page.setViewportSize({width,height:1000});
    await page.goto("/");
    await expect(page.getByRole("button",{name:"Open preloaded demo"})).toBeVisible();
    await page.getByRole("button",{name:"Papers",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Check it. Then trust it."})).toBeVisible();
    await page.getByRole("button",{name:"Records",exact:true}).click();
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:`test-results/demo/landing-${width}.png`,fullPage:true});
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    await page.getByRole("button",{name:"Open preloaded demo"}).click();
    await page.getByRole("button",{name:"Academics",exact:true}).click();
    await expect(page.getByRole("heading",{name:"Welcome, Demo workspace"})).toBeVisible();
    await expect(page.getByText("42 reference results",{exact:false})).toBeVisible();
    await expect(page.locator(".subject-list > li")).toHaveCount(10);
    await page.getByRole("combobox",{name:"View semester"}).selectOption("1");
    await expect(page.locator(".subject-list")).toContainText("APPLIED CHEMISTRY");
    await page.getByRole("combobox",{name:"View semester"}).selectOption("4");
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:`test-results/demo/academics-${width}.png`,fullPage:true});
    await page.getByRole("button",{name:"Assistant",exact:true}).click();
    await expect(page.getByText(/rule-based replies/)).toBeVisible();
    await page.request.post("/api/personal/suggestions/refresh");
    await page.getByLabel("Message",{exact:true}).fill("SQL test Friday, two hours");
    await page.getByRole("button",{name:"Ask Orbit",exact:true}).click();
    await expect(page.locator(".chat-thread article.assistant")).toContainText("120-minute");
    await expect(page.locator(".chat-thread article.assistant")).toContainText("8/10");
    const evidence=page.locator(".chat-thread .evidence-list");
    await evidence.locator("summary").click();
    await evidence.getByRole("button").first().click();
    await expect(evidence.locator(".evidence-detail")).toBeVisible();
    await page.evaluate(()=>window.scrollTo(0,0));
    await page.screenshot({path:`test-results/demo/assistant-${width}.png`,fullPage:true});
    await page.getByRole("button",{name:"Actions",exact:true}).click();
    const suggestions=page.locator(".suggestions-panel");
    if(width===390){
      await suggestions.getByRole("button",{name:"Dismiss",exact:true}).click();
      await suggestions.getByRole("button",{name:"Refresh suggestions"}).click();
      await expect(suggestions.getByRole("button",{name:"Accept action"})).toHaveCount(0);
      await suggestions.getByRole("button",{name:/Dismissed/}).click();
      await expect(suggestions.locator(".suggestion-item")).toHaveCount(1);
      // Change the supporting record: this creates new evidence, not a repeat of the dismissal.
      const rows=await (await page.request.get("/api/assessments")).json();
      const mark=rows.find(r=>r.kind==="quiz");
      const body=Object.fromEntries(["subject_id","title","max_score","assessed_on","kind","weak_topics"].map(k=>[k,mark[k]]));
      await page.request.put(`/api/assessments/${mark.id}`,{data:{...body,score:7}});
      await page.request.put(`/api/assessments/${mark.id}`,{data:{...body,score:8,title:"Illustrative demo · SQL quiz (reviewed)"}});
    }else{
      await suggestions.getByRole("button",{name:"Refresh suggestions"}).click();
      await suggestions.getByRole("button",{name:"Accept action"}).last().click();
      await suggestions.getByRole("button",{name:/Accepted/}).click();
      await expect(suggestions.locator(".suggestion-item")).toHaveCount(1);
    }
    await page.reload();
    await page.getByRole("button",{name:"Coding",exact:true}).click();
    await expect(page.getByText("136",{exact:true}).first()).toBeVisible();
    await page.getByRole("button",{name:"Papers",exact:true}).click();
    await expect(page.locator(".paper-list-card")).toHaveCount(2);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    expect(errors).toEqual([]);
  });
}

test("launcher demo route signs in directly",async({page})=>{
  await page.goto("/demo");
  await expect(page.getByRole("heading",{name:"What's on your mind, Demo?"})).toBeVisible();
});
