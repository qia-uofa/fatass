# A small pipeline: brainstorm dinner ideas, turn the keepers into a
# structured recipe collection (each with its own ingredients list), then
# compile a shopping list from the whole collection. Demonstrates the
# "{...}" transforms-block syntax (see fatass.signature.FULL_SIGNATURE)
# on a Chain-of-Tuple schema with a nested Chain-of-its-own, and a
# SingleMd summary depending on it -- each transform's own "#" comment
# is its `fatass modify` prompt (`fatass touch -p recipe_book.sig -m`
# reads it and fills the transform in right after creating it).
#
# Usage: fatass touch -p recipe_book.sig      # scaffold only
#        fatass touch -p recipe_book.sig -m   # scaffold + fill in

RecipeBook<Node>(
    Ideas<Chat prompt:str="Brainstorm dinner ideas for the week -- a mix of quick weeknight meals and one ambitious weekend project. Nothing here is final.">,
    Recipes<Chain>{
        # Read recipe_book.ideas' session artifacts. For each recipe
        # worth keeping, Recipes.extend(), then write its Info Tuple's
        # 'name', 'cuisine', and 'servings' fields.
        build(Ideas);
    }(
        Info<Tuple name cuisine servings>,
        Ingredients<Chain>(
            Info<Tuple item quantity unit>
        )
    ),
    ShoppingList<SingleMd>{
        # Read recipe_book.recipes (each item's own Ingredients child
        # Chain). Merge every recipe's ingredients into one consolidated
        # shopping list, combining quantities for the same item where
        # units match, grouped by grocery aisle. Use
        # ShoppingList.write(...).
        build(Recipes);
    }
)
